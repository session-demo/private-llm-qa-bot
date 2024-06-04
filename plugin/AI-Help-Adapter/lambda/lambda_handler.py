import json
import time
import random
import string
import re
import logging
import requests
import json
import os
import hashlib
from collections import OrderedDict


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
# 创建一个StreamHandler,用于输出到控制台
console_handler = logging.StreamHandler()
# 也可以创建一个FileHandler,用于输出到文件
# file_handler = logging.FileHandler('app.log')
console_handler.setLevel(logging.DEBUG)
logger.addHandler(console_handler)
# 创建一个Formatter对象
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# 为handler设置格式
console_handler.setFormatter(formatter)

BACKEND_API = os.environ["BACKEND_API"]
SECRET_KEY = os.environ["SECRET_KEY"]


def convertRequest(requestParams, multiround=True):
    # using unix timestamp as msgid
    timestamp = int(time.time() * 1000)
    msgid = requestParams["userId"] + requestParams["appKey"] + "_" + str(timestamp)
    if not multiround:
        # generate a random string as new session id
        chat_session_id = ''.join(random.sample(string.ascii_letters + string.digits, 8))
    else:
        chat_session_id = requestParams["ticketId"]
    question = requestParams["question"]
    convertedRequest = {
        "msgid": msgid,
        "chat_name": chat_session_id,
        "prompt": question,
        "system_role": "",
        "use_qa": "True",
        "multi_rounds": multiround,
        "hide_ref": "False",
        "system_role_prompt": "",
        "obj_prefix": "ai-content/",
        "use_stream": "False",
        "max_tokens": 8000,
        "temperature": 0.01,
        "use_trace": "False", # set True when use RAG
        "model_name": "claude-v3-sonnet",
        "template_id": "default",
        "company": "default",
        "user_id": "admin"
    }
    logger.debug("Request converted: " + json.dumps(convertedRequest))
    return convertedRequest


def generateAnswer(convertedRequest) -> requests.Response :
    originalResponse = requests.post(BACKEND_API, json=convertedRequest)
    # print(originalResponse.text, type(originalResponse.text))
    logger.debug("Original response generated: " + json.dumps(originalResponse.text))
    return originalResponse

def convertGreetingResponse(originalResponse: requests.Response):
    jsonOriginalResponse = json.loads(originalResponse.text)
    text = jsonOriginalResponse["body"][0]["choices"][0]["text"]    
    convertedResponse = {
        "flag": True if originalResponse.status_code == 200 else False,
        "code": originalResponse.status_code,
        "desc": "success" if originalResponse.status_code == 200 else jsonOriginalResponse["body"],
        "data": [{
            "type": 0,
            "id": 0,
            "content": text,
            "score": 0
        }],
        "time": int(time.time() * 1000)
    }
    logger.debug("Greetings response generated: " + str(convertedResponse))
    return convertedResponse

def generate_signature(params, secret_key):
    """
    根据给定的参数和应用密钥生成签名
    
    Args:
        params (dict): 请求参数字典
        secret_key (str): 双方约定的应用密钥
    
    Returns:
        str: 签名字符串
    """
    # 将参数和应用密钥封装成有序字典
    params['secretKey'] = secret_key
    ordered_params = OrderedDict(sorted(params.items()))
    logger.debug("Ordered params: " + str(ordered_params))
    
    # 拼接有序字典的值
    values = [str(value) for value in ordered_params.values()]
    value_string = ''.join(values).strip()
    logger.debug("Value string: " + value_string)
    
    # 计算MD5签名并转换为小写
    signature = hashlib.md5(value_string.encode('utf-8')).hexdigest().lower()
    logger.debug("Signature: " + signature)
    
    return signature

def lambda_handler(event, context):
    # TODO implement
    if BACKEND_API is None or SECRET_KEY is None:
        logger.error("Backend API or SecretKey is not set.")
        failedResponse = {
            "flag": False,
            "code": 400,
            "desc": "Backend API or SecretKey is not set.",
            "data": [],
            "time": int(time.time() * 1000)
        }
        finalResponseFailed = {
            'statusCode': 400,
            'body': json.dumps(failedResponse)
        }
    sign = event["headers"]["sign"]
    logger.debug("Sign received: " + sign)
    responseBody = json.loads(event["body"])
    validation_dict = dict(responseBody)
    sign2 = generate_signature(validation_dict, SECRET_KEY)
    logger.debug("Request received. Validating...")
    if sign != sign2:
        logger.error("Signature validation failed.")
        failedResponse =  {
            "flag": False,
            "code": 403,
            "desc": "Signature validation failed.",
            "data": [],
            "time": int(time.time() * 1000)
        }
        finalResponseFailed = {
            'statusCode': 403,
            'body': json.dumps(failedResponse)
        }
        return finalResponseFailed
    logger.debug("Signature validation passed. Generating answer...")
    convertedRequest = convertRequest(responseBody)
    originalResponse = generateAnswer(convertedRequest)
    convertedResponse = convertGreetingResponse(originalResponse)
    logger.debug("Final output: " + str(convertedResponse))
    finalResponse = {
        'statusCode': 200,
        'body': json.dumps(convertedResponse)
    }
    return finalResponse
