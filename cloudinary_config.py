import cloudinary
import os

# 尝试从环境变量获取配置
cloud_name = os.environ.get('CLOUDINARY_CLOUD_NAME', 'dhjim7xbr')
api_key = os.environ.get('CLOUDINARY_API_KEY', '149872547298524')
api_secret = os.environ.get('CLOUDINARY_API_SECRET', 'QItNLkUdG54eFYrFXfVPfCo74eM')

cloudinary.config(
    cloud_name = cloud_name,
    api_key = api_key,
    api_secret = api_secret,
    secure = True
)