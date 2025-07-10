import base64
import urllib
import requests
import json
import os


class BaiduASRClient:
    def __init__(self, api_key, secret_key, cuid="python-client"):
        self.api_key = api_key
        self.secret_key = secret_key
        self.cuid = cuid
        self.token = self.get_access_token()

    def get_access_token(self):
        """
        获取 Access Token
        """
        url = "https://aip.baidubce.com/oauth/2.0/token"
        params = {
            "grant_type": "client_credentials",
            "client_id": self.api_key,
            "client_secret": self.secret_key
        }
        print("正在获取 access_token...")
        response = requests.post(url, params=params)
        result = response.json()
        if "access_token" in result:
            print("access_token 获取成功")
            return result["access_token"]
        else:
            raise Exception("获取 access_token 失败: " + json.dumps(result, ensure_ascii=False))

    def wav_to_base64(self, path, urlencoded=False):
        """
        将 WAV 文件转为 base64 编码
        """
        with open(path, "rb") as f:
            content = base64.b64encode(f.read()).decode("utf8")
            if urlencoded:
                content = urllib.parse.quote_plus(content)
        return content

    def recognize(self, wav_path):
        """
        执行语音识别，返回识别文本
        """
        url = "https://vop.baidu.com/server_api"
        speech = self.wav_to_base64(wav_path, urlencoded=False)
        length = os.path.getsize(wav_path)

        payload = {
            "format": "wav",
            "rate": 16000,
            "channel": 1,
            "cuid": self.cuid,
            "token": self.token,
            "speech": speech,
            "len": length
        }

        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

        print(f"正在识别：{wav_path}，文件大小：{length} 字节")
        response = requests.post(url, headers=headers, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        result = response.json()
        if "result" in result:
            return result["result"][0]
        else:
            raise Exception("识别失败：" + json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    client = BaiduASRClient(
        api_key="7uRTjFlexqemPwYNV6ZiHOQR",
        secret_key="AM8FWQxpdJTLbMItZhAlyVVrD2GMhlQs",
        cuid="253ZFhUBw62MFNTNUv2hQLqRs2flE9W9"
    )

    try:
        text = client.recognize("2.wav")
        print("识别结果：", text)
    except Exception as e:
        print("出错：", e)
