from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont

def watermark_text(input, text, pos, opacity, font_size, font_color):
    image = Image.open(input).convert('RGBA')
   
    textImg = Image.new('RGBA', image.size, (255,255,255,0))
    textImg.paste(image, (0,0))
    font = ImageFont.truetype("./font.ttf", font_size)
   
    drawing = ImageDraw.Draw(textImg)
    drawing.text(pos, text, fill=font_color+hex(int(opacity*2.55))[2:], font=font)
   
    watermarked = Image.alpha_composite(image, textImg)
    watermarked.save(input)
   
def watermark_image(input, watermark, pos, opacity):
    image = Image.open(input).convert("RGBA")
    wm = Image.open(watermark).convert("RGBA")
    
    pasteMask = wm.split()[3].point(lambda i: i * opacity / 100.)
    
    transparent = Image.new('RGBA', image.size, (0,0,0,0))
    transparent.paste(image, (0,0))
    transparent.paste(wm, pos, mask=pasteMask)
    transparent.save(input)