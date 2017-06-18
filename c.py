from PIL import Image, ImageDraw, ImageFont

img = Image.open('F:\\robot_data\\xiaoyezi\\pictures\\@6ee0032bac8d6829a81497b354d92826_20170618-232614_2764.jpg')
img = img.resize((400,400), Image.LANCZOS)
target = Image.new('RGB', (400,400))
target.paste(img, (0, 0, 400, 400))
target.save('F:\\robot_data\\xiaoyezi\\pictures\\aaaaa.jpg', quality=100)


