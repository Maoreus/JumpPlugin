import os
import re
import json
import subprocess
import random
#from xx import xx  是从xx的包中获取xx的文件
import time
from PIL import Image
# 获取手机配置
def getConfig():
    size_str = os.popen("adb shell wm size").read()
    phone_size = re.compile('(\d+)x(\d+)').findall(size_str)
    screen_size = "%sx%s" % (phone_size[0][1], phone_size[0][0])
    config_path = 'config/config/%s/config.json' % screen_size
    with open(config_path, 'r') as f:
        print("config file:", config_path)
        return json.load(f)
    # print(config_path)
    #
    # print(screen_size)

# 获取截图
def getImage():
    # 这个为什么不用os  是这样的   用os也可以截图   但是截完就存手机里了...
    # 而subprocess可以存在PIPE里
    # 然后我们读取之后  存到电脑上
    process = subprocess.Popen('adb shell screencap -p', shell=True, stdout=subprocess.PIPE)
    screenshot = process.stdout.read()
    # 从管道里读出来的二进制   它不是一个正常的图片
    # 每一排像素点最后都会多出两个\r
    # 我们直接用读出来的二进制保存   会发现  文件损坏了 所以要把\r换掉
    # b是防转义
    binary_screenshot = screenshot.replace(b'\r\r\n', b'\n')
    with open('autojump.png', 'wb') as f:
        f.write(binary_screenshot)

# 获取图片中的棋子坐标--棋子是紫色的，根据元组来确定
# 获取要跳转到的盒子的坐标
def getPoint(img, con):
    w, h = img.size
    # 棋子的底边界
    piece_y_max = 0
    scan_x_side = int(w / 8)  # 扫描棋子的左右边界减少开销
    scan_start_y = 0  # 扫描起始y坐标
    img_pixel = img.load()  # 像素矩阵
    for i in range(h // 3, h * 2 // 3, 50): # //在python3中表示整除
        # first_pixel表示每行的第一个像素
        first_pixel = img_pixel[0, i]
        for j in range(1, w):
            # 如果不是纯色，说明碰到了新的棋盘，跳出
            pixel = img_pixel[j, i]
            # 每个像素去跟第一个比
            # 像这种绝对值之差大于10的我们就认为是色差很大的店
            # 也就是说障碍物只要碰到了障碍物  就可以break了
            if abs(pixel[0] - first_pixel[0]) + abs(pixel[1] - first_pixel[1]) + abs(pixel[2] - first_pixel[2]) > 10:
                # 回退50的距离，防止越界
                scan_start_y = i - 50
                break
        if scan_start_y:
            break
    # 已找到感兴趣区域，开始精确扫描
    left, right = 0, 0
    for i in range(scan_start_y, h * 2 // 3):
        flag = True
        for j in range(scan_x_side, w - scan_x_side):
            pixel = img_pixel[j, i]
            # 根据棋子的最低行的颜色判断，找最后一行那些点的平均值
            # 这里的判断条件是r,g,b，紫色也是由三原色构成的，这是它的范围
            if (50 < pixel[0] < 60) and (53 < pixel[1] < 63) and (95 < pixel[2] < 110):
                # 扫描一行，紫色的最左边和最右边
                if flag:
                    left = j
                    flag = False
                right = j
                piece_y_max = i
    piece_x = (left + right) // 2
    piece_y = piece_y_max - con['piece_base_height_1_2']  # 上调高度，根据分辨率自行 调节
    print(piece_x, piece_y)

    # 缩小搜索范围-----确定盒子的边界
    if piece_x < w / 2:  # 棋子在左边，那目标盒子就在右边
        board_x_start = piece_x + con["piece_body_width"] // 2
        board_x_end = w
    else:  # 棋子在右边，那目标盒子一定在左边
        board_x_start = 0
        board_x_end = piece_x - con["piece_body_width"] // 2

    # 精确扫描
    left, right, num = 0, 0, 0
    for i in range(h // 3, h * 2 // 3):
        flag = True
        first_pixel = img_pixel[0, i]
        for j in range(board_x_start, board_x_end):
            pixel = img_pixel[j, i]
            # 找到第一个不同色的，也就是最高点
            if abs(pixel[0] - first_pixel[0]) + abs(pixel[1] - first_pixel[1]) + abs(pixel[2] - first_pixel[2]) > 10:
                if flag:
                    left, flag = j, False
                right, num = j, num + 1
                # print(left, right)
        if not flag: break
    board_x = (left + right) // 2
    top_point = img_pixel[board_x, i + 1]  # 最高点的像素

    # 用最高点的y增加一个估计值，然后从下往上找   274这个值有待调节
    for k in range(i + 274, i, -1):
        pixel = img_pixel[board_x, k]
        # print(pixel)
        # rgb的差小于10认为是同色
        if abs(pixel[0] - top_point[0]) + abs(pixel[1] - top_point[1]) + abs(pixel[2] - top_point[2]) < 10:
            break
    # 盒子最高和最低点x坐标是一样的，中心点的y坐标是上下取均值
    board_y = (i + k) // 2
    # num表示最高点的数量
    # 这个判断条件有待改进
    if num < 5 and k - i < 30:
        # 去除有些颜色比较多的误差
        print('杂色')
        board_y += (k - i)
        if piece_x < w / 2:  # 棋子在左边
            board_x -= (k - i)
        else:
            board_x += (k - i)
    # 药瓶是特殊的
    # rgb都是255  就代表白色
    if top_point[:-1] == (255, 255, 255): # a[:-1]  就是把0和-1之间的位置截下来,python的反向索引
        print('药瓶')
        board_y = (i + board_y) // 2

    return piece_x, piece_y, board_x, board_y

# 跳一跳，传入距离、按压点和压力系数
def jump(distance, point, ratio):
    press_time = distance * ratio
    # 如果两个点距离很近会导致按压时间严重不够，所以设置最小按压时间
    press_time = int(max(press_time, 100))  # 最小按压时间

    # adb命令模拟按压
    # 每个点两个坐标  x和y   所以总共5个参数
    cmd = 'adb shell input swipe %d %d %d %d %d' % (point[0], point[1], point[0], point[1], press_time)
    print(cmd)
    os.system(cmd)
    return press_time


if __name__== '__main__':
    config = getConfig()
    while True:
        # Image可以帮助我们把二进制文件变成一个可以操作的随想
        img = Image.open('autojump.png')
        piece_x, piece_y, board_x, board_y = getPoint(img, config)
        print(piece_x, piece_y, '------->', board_x, board_y)
        # **是python里的幂运算 ^只代表异或
        # 棋子中心和盒子中心的距离
        distance = ((board_x - piece_x) ** 2 + (board_y - piece_y) ** 2) ** 0.5
        # 按压点随机产生
        press_point = (random.randint(100, 500), random.randint(100, 500))
        jump(distance, press_point, config['press_ratio'])
        time.sleep(random.randrange(1, 2))



# 图像是不是就是一个矩阵呀
# 由像素点组成的对不对呀
# 然后每个像素点其实是一个元祖  有四个值  是(r,g,b,a)
# r g b就是  三原色嘛  0~255之间的  a是透明度

