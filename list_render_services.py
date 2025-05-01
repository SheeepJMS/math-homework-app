import os
import requests
import json

def list_render_services():
    # Render API配置
    RENDER_API_KEY = os.environ.get('RENDER_API_KEY')
    if not RENDER_API_KEY:
        print("请设置RENDER_API_KEY环境变量")
        return False
    
    API_URL = "https://api.render.com/v1/services"
    
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {RENDER_API_KEY}"
    }
    
    try:
        # 获取所有服务
        response = requests.get(API_URL, headers=headers)
        response.raise_for_status()
        services = response.json()
        
        print("\n可用的服务：")
        print("-" * 50)
        for service in services:
            print(f"服务名称: {service['name']}")
            print(f"服务ID: {service['id']}")
            print(f"服务类型: {service['type']}")
            print(f"状态: {service['status']}")
            print("-" * 50)
        
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"获取服务列表失败: {str(e)}")
        return False

if __name__ == '__main__':
    list_render_services() 