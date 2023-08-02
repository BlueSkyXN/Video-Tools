
import os
import re
import subprocess
import concurrent.futures
import logging
import datetime

# 获取当前时间的字符串表示形式
timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')

# 路径配置，需要先自行确认文件夹存在
input_folder_path = r'E:\Cache\input'
output_folder_path = r'E:\Cache\output'
log_folder_path = r'E:\Cache\log'

# 设置临时文件夹
env = os.environ.copy()
temp_folder = r'E:\Cache\log'
env['TMP'] = temp_folder
env['TEMP'] = temp_folder

# 检查临时文件夹是否存在，如果不存在，则创建它
os.makedirs(temp_folder, exist_ok=True)

# 配置日志记录器，将时间戳添加到文件名中
logging.basicConfig(filename=f'{log_folder_path}\\transcoding_{timestamp}.log', level=logging.INFO)

# 获取视频文件的码率
def get_bitrate(filepath):
    cmd = f'ffprobe -v error -show_entries format=bit_rate -of default=noprint_wrappers=1:nokey=1 "{filepath}"'
    output = subprocess.check_output(cmd, shell=True, env=env).decode('utf-8').strip()
    return int(output)

# Get the resolution of a video file
def get_resolution(filepath):
    cmd = f'ffprobe -v error -show_entries stream=width,height -of csv=p=0 "{filepath}"'
    output = subprocess.check_output(cmd, shell=True, env=env).decode('utf-8').strip().split(',')
    return int(output[0]), int(output[1])

# 压缩视频文件
def compress_file(filepath):
    try:
        # 计算压缩后的码率（40%的原始码率）
        original_bitrate = get_bitrate(filepath)
        new_bitrate = int(original_bitrate * 0.4)

        # Get the resolution of the video
        width, height = get_resolution(filepath)

        # Determine the maximum bitrate based on the resolution
        #720P-最大2M码率
        #1080P-最大4M码率
        #2K-最大10M码率
        #2K往上-最大20M码率
        short_side = min(width, height)
        if short_side <= 720:
            max_bitrate = 2000000
        elif short_side <= 1080:
            max_bitrate = 4000000
        elif short_side <= 1440:
            max_bitrate = 10000000
        else:
            max_bitrate = 20000000

        # Limit the new bitrate to the maximum bitrate
        new_bitrate = min(new_bitrate, max_bitrate)

        # 生成新的文件名
        new_filename = os.path.join(output_folder_path, os.path.relpath(filepath, input_folder_path))
        new_dirname = os.path.dirname(new_filename)
        os.makedirs(new_dirname, exist_ok=True)

        # 执行压缩命令
        if os.path.exists(new_filename):
            logging.info(f"文件 {new_filename} 已经存在，跳过")
            return None
        cmd = f'ffmpeg -err_detect ignore_err -i "{filepath}" -c:v hevc_nvenc -b:v {new_bitrate} -c:a aac "{new_filename}"'
        subprocess.check_call(cmd, shell=True, env=env)  # 这里我们使用 check_call，如果命令返回非零值，则抛出 CalledProcessError
        #使用N卡的HEVC编码器编码视频，音频用aac，也可以改成copy
        
        # 记录日志
        logging.info(f'Successfully compressed: {filepath} from {original_bitrate} to {new_bitrate}. New file: {new_filename}')

        # 如果压缩成功，返回 None
        return None

    except subprocess.CalledProcessError as e:
        # ffmpeg命令出错，记录错误信息到日志
        logging.error(f'Failed to compress {filepath}. Error: {str(e)}')

        # 返回错误信息
        return str(e)

# Get all video files recursively
def get_video_files(input_folder_path):
    video_files = []
    for root, _, files in os.walk(input_folder_path):
        for file in files:
            if file.endswith(('.mp4', '.mkv', '.ts', '.avi', '.rm', '.rmvb', '.wmv')):
                video_files.append(os.path.join(root, file))
    return video_files


# 获取输入文件夹中的所有视频文件
video_files = get_video_files(input_folder_path)

# 创建一个线程池，注意自己换线程数，取决于你的显卡，自己去官网查，比如现在RTX4080是2核5线程，不可以超过线程数
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
    # 将任务提交到线程池，收集结果
    results = executor.map(compress_file, video_files)

# 检查结果，处理错误
for filepath, error in zip(video_files, results):
    if error is not None:
        logging.error(f'Skipping file {filepath} due to error: {error}')
