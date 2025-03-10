import re
import sys
import threading
import atexit
from readerwriterlock import rwlock
from flask import Flask, request, jsonify
from datetime import datetime
from flasgger import Swagger
import json
from jsonpath_ng import jsonpath, parse
from enum import Enum
import os
from test2 import GET_task_path
import numpy as np
import logging
app = Flask(__name__)
swagger = Swagger(app)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_json(path):
    file_path = path + '.json'
    if not os.path.exists(file_path):
        with open(file_path, 'w') as file:
            json.dump({}, file)  # 创建一个新的空文件并写入空字典
        return {}
    with open(file_path, 'r') as file:
        return json.load(file)
# 模拟数据库
user_lock = rwlock.RWLockFairD()  #用户读写锁
users = {}# 用户数据 json

packages_lock = rwlock.RWLockFairD() #包裹读写锁
packages = {}# 包裹数据 json

deliveries_lock = rwlock.RWLockFairD() # 配送任务读写锁
deliveries = {}# 配送任务数据 json

orders_lock = rwlock.RWLockFairD() #订单读写锁
orders = {}# 订单数据 json

# 缓存每个快递员当天的任务路径和相关信息
cached_tasks = {}

# 在应用程序退出时执行的操作
def save_json(path, data):
    file_path = path + '.json'
    # 将所有 Order 对象转换为字典格式
    serializable_data = {k: (v.to_dict() if hasattr(v, 'to_dict') else v) for k, v in data.items()}
    try:
        with open(file_path, 'w') as file:  # 使用 'w' 模式打开文件，确保覆写文件内容
            json.dump(serializable_data, file, indent=4)
        logger.info(f"Saved JSON data to {file_path}")
    except Exception as e:
        logger.error(f"An error occurred while saving JSON to {file_path}: {e}")

def save_data():
    save_json('orders',orders)
    save_json('deliveries',deliveries)
    save_json('packages',packages)
    save_json('users',users)
    print("数据已保存")

# 注册退出时执行的操作
atexit.register(save_data)
class UserRole(str,Enum):
    USER = 'user'
    COURIER = 'courier'
class PackageState(str,Enum):
    UNCOUNTED = 'uncounted'#未入库
    COUNTED = 'counted'#已入库
    DISPATCHED = 'dispatched'#已出库
class DeliveryState(str,Enum):
    PENDING = 'pending'
    INTRANSIT = 'intransit'
    DELIVERED = 'delivered'
    RECEIVED = 'received'
class OrderState(str, Enum):
    PLACED = 'placed'  # 已下单 (订单创建)
    RECEIVED = 'received'  # 已接入（包裹运达本地配送中心）
    COMPLETED = 'completed'  # 已完成
    CANCELED = 'canceled'  # 已取消
class User:
    def __init__(self, username, password, address, contact, online=False,role=UserRole.USER):
        self.username = username
        self.password = password
        self.address = address
        self.contact = contact
        self.role = role
        self.online = online
    def to_dict(self):
        return {
            'username': self.username,
            'password': self.password,
            'address': self.address,
            'contact': self.contact,
            'role': self.role,
            'online': self.online
        }
class Package:
    def __init__(self, package_id, sender, receiver, status=PackageState.UNCOUNTED):
        self.package_id = package_id
        self.sender = sender
        self.receiver = receiver
        self.status = status
        self.created_at = datetime.now()
        self.completed_at = None
        self.history = [(status, self.created_at)]
    def to_dict(self):
        return {
            'package_id': self.package_id,
            'sender': self.sender,
            'receiver': self.receiver,
            'status': self.status.value,
            'created_at': self.created_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'history': [(status.value, timestamp.isoformat()) for status, timestamp in self.history]
        }
class Delivery:
    def __init__(self, delivery_id, package_id, courier_name, status=DeliveryState.PENDING):
        self.delivery_id = delivery_id
        self.package_id = package_id
        self.courier_name = courier_name
        self.status = status
        self.history = [(status, datetime.now())]
    def to_dict(self):
        return {
            'delivery_id': self.delivery_id,
            'package_id': self.package_id,
            'courier_name': self.courier_name,
            'status': self.status.value,
            'history': [(status.value, timestamp.isoformat()) for status, timestamp in self.history]
        }
class Order:
    def __init__(self, order_id, sender_name, receiver_name, sender_address, receiver_address,package_id,priority,status=OrderState.PLACED):
        self.order_id = order_id
        self.sender_name = sender_name
        self.receiver_name = receiver_name
        self.sender_address = sender_address
        self.receiver_address = receiver_address
        self.package_id = package_id
        self.priority = priority
        self.status = status
        self.history =[[status,datetime.now()]]
    def to_dict(self):
        return {
            'order_id': self.order_id,
            'sender_name': self.sender_name,
            'receiver_name': self.receiver_name,
            'sender_address': self.sender_address,
            'receiver_address': self.receiver_address,
            'package_id': self.package_id,
            'priority': self.priority,
            'status': self.status.value,
            'history': [(status.value, timestamp.isoformat()) for status, timestamp in self.history]  # 处理为列表
        }
def update_package_status_logic(package_id, status):
    lock = packages_lock.gen_wlock()
    if not lock.acquire(timeout=5):
        return {'success': False, 'message': '获取写锁超时'}, 500

    try:
        package = packages.get(package_id)
        if package:
            package['status'] = status
            package['history'].append((status, datetime.now()))
            return {'success': True, 'message': '包裹状态更新成功'}, 200
        else:
            return {'success': False, 'message': '包裹未找到'}, 404
    finally:
        lock.release()
def update_order_status_logic(order_id, status):
    lock = orders_lock.gen_wlock()
    if not lock.acquire(timeout=5):
        return {'success': False, 'message': '获取写锁超时'}, 500

    try:
        order = orders.get(order_id)
        if order:
            order['status'] = status
            order['history'].append((status, datetime.now()))
            return {'success': True, 'message': '包裹状态更新成功'}, 200
        else:
            return {'success': False, 'message': '包裹未找到'}, 404
    finally:
        lock.release()
def Create_Delivery(delivery_id,package_id,courier_id):
    lock = deliveries_lock.gen_wlock()
    if not lock.acquire(timeout=5):
        return TimeoutError()
    try:
        if delivery_id in deliveries:
            return jsonify({'success': False, 'message': '配送任务已存在'}), 400
        delivery = Delivery(delivery_id, package_id, courier_id)
        deliveries[delivery_id] = delivery.to_dict()
    finally:
        lock.release()
def Create_Order(order_id, sender_name, receiver_name, sender_address, receiver_address, package_id,priority=0):
    lock = orders_lock.gen_wlock()
    if not lock.acquire(timeout=5):
        raise TimeoutError("获取写锁超时")
    try:
        if order_id in orders:
            return {'success': False, 'message': '订单已存在'}, 400
        order = Order(order_id, sender_name, receiver_name, sender_address, receiver_address, package_id,priority)
        orders[order_id] = order.to_dict()
        return {'success': True, 'message': '订单创建成功'}, 201
    finally:
        lock.release()
# 用户管理
@app.route('/user/register', methods=['POST'])
def register_user():
    """
    用户注册
    ---
    tags: [用户管理]
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [username, password, address, contact]
          properties:
            username: {type: string}
            password: {type: string}
            address: {type: string}
            contact: {type: string}
    responses:
      201: {description: 用户注册成功}
      400: {description: 用户已存在或输入无效}
    """
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    # 验证用户名和密码是否包含空格或非法字符
    if not re.match(r'^[a-zA-Z0-9_]+$', username):
        return jsonify({'success': False, 'message': '无效的用户名。只允许字母、数字和下划线。'}), 400
    if not re.match(r'^[a-zA-Z0-9_]+$', password):
        return jsonify({'success': False, 'message': '无效的密码。只允许字母、数字和下划线。'}), 400

    lock = user_lock.gen_wlock()
    if not lock.acquire(timeout=5):
        return jsonify({'success': False, 'mes sage': '获取写锁超时'}), 500

    try:
        if username in users:
            return jsonify({'success': False, 'message': '用户已存在'}), 400

        user = User(username, password, data.get('address'), data.get('contact'))
        users[username] = user.to_dict()
    finally:
        lock.release()

    return jsonify({'success': True, 'message': '用户注册成功'}), 201
@app.route('/user/login', methods=['POST'])
def login_user():
    """
    用户登录
    ---
    tags: [用户管理]
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [username, password]
          properties:
            username: {type: string}
            password: {type: string}
    responses:
      200: {description: 登录成功}
      401: {description: 无效的凭证}
    """
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    lock = user_lock.gen_rlock()
    if not lock.acquire(timeout=5):
        return jsonify({'success': False, 'message': '获取读锁超时'}), 500

    try:
        user = users.get(username)
        print(f'{username} has logged in')
        if user and user['password'] == password:
            lock.release()
            lock = user_lock.gen_wlock()
            if not lock.acquire(timeout=5):
                return jsonify({'success': False, 'message': '获取写锁超时'}), 500
            try:
                user['online'] = True
            finally:
                lock.release()
                return jsonify({'success': True, 'message': '登录成功'}), 200
        else:
            lock.release()
            return jsonify({'success': False, 'message': '无效的凭证(密码错误)'}), 401
    except:
        return jsonify({'success': False, 'message': '用户未找到'}), 404
@app.route('/user/<username>', methods=['GET'])
def get_user_info(username):
    """
    获取用户信息
    ---
    tags: [用户管理]
    parameters:
      - in: path
        name: username
        required: true
        type: string
    responses:
      200: {description: 成功获取用户信息}
      404: {description: 用户未找到}
    """
    lock = user_lock.gen_rlock()
    if not lock.acquire(timeout=5):
        return jsonify({'success': False, 'message': '获取读锁超时'}), 500

    try:
        user_data = users.get(username)
        if user_data:
            # 确保 user_data 是一个字典
            return jsonify({'success': True, 'user': user_data}), 200
    finally:
        lock.release()

    return jsonify({'success': False, 'message': '用户未找到'}), 404

@app.route('/user/<username>', methods=['PUT'])
def update_user_info(username):
    """
    更新用户信息
    ---
    tags: [用户管理]
    parameters:
      - in: path
        name: username
        required: true
        type: string
        description: 用户名
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            password:
              type: string
              description: 新密码
            contact:
              type: string
              description: 新联系方式
            role:
              type: string
              description: 新角色
              enum: [user, courier]
            address:
              type: string
              description: 新地址
    responses:
      200:
        description: 用户信息更新成功
        schema:
          type: object
          properties:
            success:
              type: boolean
              description: 请求是否成功
            message:
              type: string
              description: 响应消息
      404:
        description: 用户未找到
        schema:
          type: object
          properties:
            success:
              type: boolean
              description: 请求是否成功
            message:
              type: string
              description: 响应消息
      500:
        description: 获取写锁超时
        schema:
          type: object
          properties:
            success:
              type: boolean
              description: 请求是否成功
            message:
              type: string
              description: 响应消息
    """
    data = request.get_json()

    lock = user_lock.gen_wlock()
    if not lock.acquire(timeout=5):
        return jsonify({'success': False, 'message': '获取写锁超时'}), 500
    try:
        user_data = users.get(username)
        if user_data:
            # 确保 user_data 是一个字典
            if isinstance(user_data, str):
                user_data = json.loads(user_data)
            user = User(**user_data)
            user.contact = data.get('contact', user.contact)
            user.password = data.get('password', user.password)
            user.role = UserRole(data.get('role', user.role))
            user.address = data.get('address', user.address)

            # 更新用户字典
            users[username] = user.to_dict()

            return jsonify({'success': True, 'message': '用户信息更新成功'}), 200
    finally:
        lock.release()

    return jsonify({'success': False, 'message': '用户未找到'}), 404
# 包裹管理
@app.route('/package/create', methods=['POST'])
def create_package():
    """
    创建包裹
    ---
    tags: [包裹管理]
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [package_id, sender, receiver]
          properties:
            package_id: {type: string}
            sender: {type: string}
            receiver: {type: string}
    responses:
      201: {description: 包裹创建成功}
      400: {description: 包裹已存在}
    """
    data = request.get_json()
    package_id = data.get('package_id')

    lock = packages_lock.gen_wlock()
    if not lock.acquire(timeout=5):
        return jsonify({'success': False, 'message': '获取写锁超时'}), 500

    try:
        if package_id in packages:
            return jsonify({'success': False, 'message': '包裹已存在'}), 400
        package = Package(package_id, data.get('sender'), data.get('receiver')).to_dict()
        packages[package_id] = package.to_dict()
    finally:
        lock.release()

    return jsonify({'success': True, 'message': '包裹创建成功'}), 201
@app.route('/package/<package_id>', methods=['GET'])
def get_package_status(package_id):
    """
    获取包裹状态
    ---
    tags: [包裹管理]
    parameters:
      - in: path
        name: package_id
        required: true
        type: string
    responses:
      200: {description: 成功获取包裹状态}
      404: {description: 包裹未找到}
    """
    lock = packages_lock.gen_rlock()
    if not lock.acquire(timeout=5):
        return jsonify({'success': False, 'message': '获取读锁超时'}), 500

    try:
        package = packages.get(package_id)
        if package:
            return jsonify({'success': True, 'package': {'package_id': package['package_id'], 'status': package['status'], 'history': package['history']}}), 200
    finally:
        lock.release()

    return jsonify({'success': False, 'message': '包裹未找到'}), 404
@app.route('/package/<package_id>', methods=['PUT'])
def update_package_status(package_id):
    """
    更新包裹状态
    ---
    tags: [包裹管理]
    parameters:
      - in: path
        name: package_id
        required: true
        type: string
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            status: {type: string}
    responses:
      200: {description: 包裹状态更新成功}
      404: {description: 包裹未找到}
    """
    data = request.get_json()
    status = data.get('status')

    if not status:
        return jsonify({'success': False, 'message': '缺少状态信息'}), 400

    result, status_code = update_package_status_logic(package_id, status)
    return jsonify(result), status_code
#订单管理
@app.route('/orders/receiver/<receiver_name>', methods=['GET'])
def get_orders_by_receiver(receiver_name):
    """
    获取某收件人的所有订单
    ---
    tags: [订单管理]
    parameters:
      - in: path
        name: receiver_name
        required: true
        type: string
    responses:
      200: {description: 成功获取订单列表}
      404: {description: 未找到订单}
    """
    
    lock = orders_lock.gen_rlock()
    if not lock.acquire(timeout=5):
        return jsonify({'success': False, 'message': '获取读锁超时'}), 500
    try:
        receiver_orders = [
            order for order in orders.values()
            if order['receiver_name'] == receiver_name
        ]
        if receiver_orders:
            return jsonify({'success': True, 'orders': receiver_orders}), 200
    finally:
        lock.release()

    return jsonify({'success': False, 'message': '未找到订单'}), 404
@app.route('/order', methods=['POST'])
def create_order():
    """
    创建订单
    ---
    tags: [订单管理]
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [order_id, sender_name, receiver_name, sender_address, receiver_address, package_id]
          properties:
            order_id: {type: string}
            sender_name: {type: string}
            receiver_name: {type: string}
            sender_address: {type: string}
            receiver_address: {type: string}
            package_id: {type: string}
            priority: {type: integer}
    responses:
      201: {description: 订单创建成功}
      400: {description: 订单已存在}
    """
    data = request.get_json()
    order_id = data.get('order_id')
    sender_name = data.get('sender_name')
    receiver_name = data.get('receiver_name')
    sender_address = data.get('sender_address')
    receiver_address = data.get('receiver_address')
    package_id = data.get('package_id')
    priority = data.get('priority')

    if not order_id or not sender_name or not receiver_name or not sender_address or not receiver_address or not package_id:
        return jsonify({'success': False, 'message': '缺少必要的订单信息'}), 400
    Create_Order(order_id, sender_name, receiver_name, sender_address, receiver_address, package_id,priority)
    
    return jsonify({'success': True, 'message': '订单创建成功'}), 201
@app.route('/order/<order_id>', methods=['PUT'])
def update_order_status(order_id):
    """
    更新订单状态
    ---
    tags: [订单管理]
    parameters:
      - in: path
        name: order_id
        required: true
        type: string
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            status: {type: string}
    responses:
      200: {description: 订单状态更新成功}
      404: {description: 订单未找到}
    """
    data = request.get_json()
    status = data.get('status')

    if not status:
        return jsonify({'success': False, 'message': '缺少状态信息'}), 400

    result, status_code = update_order_status_logic(order_id, status)
    return jsonify(result), status_code
@app.route('/order/<order_id>', methods=['GET'])
def get_order_info(order_id):
    """
    获取订单信息
    ---
    tags: [订单管理]
    parameters:
      - in: path
        name: order_id
        required: true
        type: string
    responses:
      200:
        description: 成功获取订单信息
        schema:
          type: object
          properties:
            order_id: {type: string}
            sender_name: {type: string}
            receiver_name: {type: string}
            sender_address: {type: string}
            receiver_address: {type: string}
            package_id: {type: string}
            priority: {type: integer}
            status: {type: string}
            history:
              type: array
              items:
                type: object
                properties:
                  status: {type: string}
                  timestamp: {type: string}
      404:
        description: 订单未找到
    """
    lock = orders_lock.gen_rlock()
    if not lock.acquire(timeout=5):
        return jsonify({"error": "获取读锁超时"}), 500

    try:
        order = orders.get(order_id)
        if order:
            return jsonify(order), 200
        else:
            return jsonify({"error": "订单未找到"}), 404
    finally:
        lock.release()

# 配送管理
@app.route('/delivery/assign/<username>', methods=['POST'])
def assign_delivery(username):
    """
    分配订单配送任务
    ---
    tags: [配送管理]
    parameters:
      - in: path
        name: username
        required: true
        type: string
    responses:
      201: {description: 配送任务分配成功} 
      400: {description: 配送任务已存在}
    """
    today = datetime.now().date()

    if not username:
        return jsonify({'success': False, 'message': '缺少快递员信息'}), 400

    # 检查是否已经生成过该快递员当天的任务
    if username in cached_tasks and cached_tasks[username]['date'] == today:
        return jsonify({
            'success': True,
            'message': '配送任务分配成功',
            'path': cached_tasks[username]['total_path'],
            'length': cached_tasks[username]['total_length'],
            'clusters_path': cached_tasks[username]['clusters_path'],
            'clusters_length': cached_tasks[username]['clusters_length']
        }), 201
    lock = orders_lock.gen_rlock()
    if not lock.acquire(timeout=5):
        return jsonify({'success': False, 'message': '获取读锁超时'}), 500
        
    try:
        today_orders = [
            {'order_id': order['order_id'], 'receiver_address': order['receiver_address'], 'status': order['status']}
            for order in orders.values()
            if order['status'] == OrderState.RECEIVED.value
        ]
        
        coordinates = [order['receiver_address'] for order in today_orders]
        print(coordinates)
        total_path, total_length, clusters_path, clusters_length = GET_task_path(coordinates)
        total_path = list(map(lambda x: today_orders[x]['order_id'], total_path))  # 从下标转换成订单ID
        for x in total_path:
            update_package_status_logic(x, PackageState.DISPATCHED)   
            Create_Delivery(x,x,username) 
        # 缓存该快递员当天的任务路径和相关信息
        cached_tasks[username] = {
            'date': today,
            'total_path': total_path,
            'total_length': total_length,
            'clusters_path': clusters_path,
            'clusters_length': clusters_length
        }
    finally:
        lock.release()
    #for order in total_path:
    #    Create_Delivery(order,order,username)
    #    pass
    return jsonify({
        'success': True,
        'message': '配送任务分配成功',
        'path': total_path,
        'length': total_length,
        'clusters_path': clusters_path,
        'clusters_length': clusters_length
    }), 201
@app.route('/delivery/create/', methods=['POST'])
def create_delivery():
    """
    创建配送任务
    ---
    tags: [配送管理]
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [delivery_id, package_id, courier_name]
          properties:
            delivery_id: {type: string}
            package_id: {type: string}
            courier_name: {type: string}
    responses:
      201: {description: 配送任务创建成功}
      400: {description: 配送任务已存在}
    """
    data = request.get_json()
    delivery_id = data.get('delivery_id')
    package_id = data.get('package_id')
    courier_name = data.get('courier_name')
    if not delivery_id or not package_id or not courier_name:
        return jsonify({'success': False, 'message': '缺少必要的配送任务信息'}), 400
    try:
        Create_Delivery(delivery_id,package_id,courier_name)
    except:
        return jsonify({'success': False, 'message': '创建任务失败'}), 500
    return jsonify({'success': True, 'message': '配送任务创建成功'}), 201

@app.route('/delivery/<delivery_id>', methods=['GET'])
def get_delivery_status(delivery_id):
    """
    获取配送状态
    ---
    tags: [配送管理]
    parameters:
      - in: path
        name: delivery_id
        required: true
        type: string
    responses:
      200: {description: 成功获取配送状态}
      404: {description: 配送任务未找到}
    """
    lock = deliveries_lock.gen_rlock()
    if not lock.acquire(timeout=5):
        return jsonify({'success': False, 'message': '获取读锁超时'}), 500

    try:
        delivery = deliveries.get(delivery_id)
        if delivery:
            return jsonify({'success': True, 'delivery': delivery}), 200
    finally:
        lock.release()

    return jsonify({'success': False, 'message': '配送任务未找到'}), 404
@app.route('/delivery/<delivery_id>', methods=['PUT'])
def update_delivery_status(delivery_id):
    """
    更新配送状态
    ---
    tags: [配送管理]
    parameters:
      - in: path
        name: delivery_id
        required: true
        type: string
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            status: {type: string}
    responses:
      200: {description: 配送状态更新成功}
      404: {description: 配送任务未找到}
    """
    data = request.get_json()

    lock = deliveries_lock.gen_wlock()
    if not lock.acquire(timeout=5):
        return jsonify({'success': False, 'message': '获取写锁超时'}), 500

    try:
        delivery = deliveries.get(delivery_id)
        if delivery:
            delivery['status'] = data.get('status', delivery['status'])
            delivery['history'].append((delivery['status'], datetime.now()))
            return jsonify({'success': True, 'message': '配送状态更新成功'}), 200
    finally:
        lock.release()

    return jsonify({'success': False, 'message': '配送任务未找到'}), 404
# 通知系统（示例）

@app.route('/notify/<username>', methods=['POST'])
def notify_after_login(username):
    """
    登录通知
    ---
    tags: [通知系统]
    parameters:
      - in: path
        name: username
        required: true
        type: string
    responses:
      200: {description: 通知发送成功}
    """
    if not username:
        return jsonify({'success': False, 'message': '缺少用户名'}), 400
    # 获取用户信息
    user_data = users.get(username)
    if not user_data:
        return jsonify({'success': False, 'message': '用户未找到'}), 404

    # 确保 user_data 是一个 User 类实例
    if isinstance(user_data, dict):
        user = User(**user_data)
    else:
        user = user_data

    # 根据用户角色返回不同的响应
    if user.role == 'user':
        # 获取用户订单状态
        order_notification = get_user_order_status(username)

        return jsonify({'success': True, 'message': '已发送', 'notification': order_notification}), 200
    elif user.role == 'courier':
        # 获取快递员任务状态
        task_notification = get_courier_task_status(username)
        return jsonify({'success': True, 'message': '已发送', 'notification': task_notification}), 200
    else:
        return jsonify({'success': False, 'message': '未知的用户角色'}), 400
def get_user_order_status(username):
    today = datetime.now().date()
    placed = sum(1 for order in orders.values() if order['status'] == 'placed' and order['receiver_name'] == username)
    received_today = sum(1 for order in orders.values() if order['status'] == 'received' and order['receiver_name'] == username and datetime.strptime(order['date_received'], '%Y-%m-%d').date() == today)
    completed_today = sum(1 for order in orders.values() if order['status'] == 'completed' and order['receiver_name'] == username and datetime.strptime(order['date_completed'], '%Y-%m-%d').date() == today)
    return f'仍处于已下单状态订单{placed}个,今天已有{received_today}个订单接入本配送中心,今天已完成{completed_today}个订单'
def get_courier_task_status(username):
    today = datetime.now().date()
    if username in cached_tasks and cached_tasks[username]['date'] == today:
        pending_tasks = len([task for task in cached_tasks[username]['total_path'] if deliveries[task]['status'] != 'delivered'])
        return  f'今日还有{pending_tasks}个配送任务待完成'
    else:
        return  f'今日还未签到,请获取配送任务'

# 统计和报告（示例）
@app.route('/report/packages', methods=['GET'])
def report_packages():
    """
    包裹数量统计
    ---
    tags: [统计和报告]
    responses:
      200: {description: 包裹数量统计生成成功}
    """
    # 这里可以实现包裹数量统计逻辑
    return jsonify({'success': True, 'message': '包裹数量统计生成成功'}), 200
@app.route('/report/deliveries', methods=['GET'])
def report_deliveries():
    """
    配送效率统计
    ---
    tags: [统计和报告]
    responses:
      200: {description: 配送效率统计生成成功}
    """
    # 这里可以实现配送效率统计逻辑
    return jsonify({'success': True, 'message': '配送效率统计生成成功'}), 200
if __name__ == '__main__':
    users=load_json('users')
    packages=load_json('packages')
    deliveries=load_json('deliveries')
    orders=load_json('orders')
    for i in range(20,40):  # 生成10个订单
        order = Order(
            order_id=i,
            sender_name=1,
            receiver_name=1,
            sender_address=[1,1],
            receiver_address=[np.random.uniform(0,10000),np.random.uniform(0,10000)],
            package_id=1,
            priority=0,
            status=OrderState.RECEIVED
        )
        orders[str(i)]=order.to_dict()
    app.run(host='0.0.0.0', port=5000)