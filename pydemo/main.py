import re
import sys
import threading
from readerwriterlock import rwlock
from flask import Flask, request, jsonify
from datetime import datetime
from flasgger import Swagger
from jsonpath_ng import jsonpath, parse
from enum import Enum

app = Flask(__name__)
swagger = Swagger(app)

# 模拟数据库
user_lock = rwlock.RWLockFairD()
users = {}

packages_lock = rwlock.RWLockFairD()
packages = {}

deliveries_lock = rwlock.RWLockFairD()
deliveries = {}

class User:
    def __init__(self, username, password, address, contact):
        self.username = username
        self.password = password
        self.address = address
        self.contact = contact

class PackageState(Enum):
    CREATED = 'created'
    ASSIGNED = 'assigned'
    DELIVERED = 'delivered'
class Package:
    def __init__(self, package_id, sender, receiver, status=PackageState.CREATED.value):
        self.package_id = package_id
        self.sender = sender
        self.receiver = receiver
        self.status = status
        self.created_at = datetime.now()
        self.completed_at = None
        self.history = [(status, self.created_at)]

class Delivery:
    def __init__(self, delivery_id, package_id, courier, status='assigned'):
        self.delivery_id = delivery_id
        self.package_id = package_id
        self.courier = courier
        self.status = status
        self.history = [(status, datetime.now())]

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
        return jsonify({'success': False, 'message': '获取写锁超时'}), 500

    try:
        if username in users:
            return jsonify({'success': False, 'message': '用户已存在'}), 400

        user = User(username, password, data.get('address'), data.get('contact'))
        users[username] = user
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
        if user and user.password == password:
            return jsonify({'success': True, 'message': '登录成功'}), 200
    finally:
        lock.release()

    return jsonify({'success': False, 'message': '无效的凭证'}), 401

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
        user = users.get(username)
        if user:
            return jsonify({'success': True, 'user': {'username': user.username, 'address': user.address, 'contact': user.contact}}), 200
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
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            address: {type: string}
            contact: {type: string}
    responses:
      200: {description: 用户信息更新成功}
      404: {description: 用户未找到}
    """
    data = request.get_json()

    lock = user_lock.gen_wlock()
    if not lock.acquire(timeout=5):
        return jsonify({'success': False, 'message': '获取写锁超时'}), 500

    try:
        user = users.get(username)
        if user:
            user.address = data.get('address', user.address)
            user.contact = data.get('contact', user.contact)
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
        package = Package(package_id, data.get('sender'), data.get('receiver'))
        packages[package_id] = package
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
            return jsonify({'success': True, 'package': {'package_id': package.package_id, 'status': package.status, 'history': package.history}}), 200
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

    lock = packages_lock.gen_wlock()
    if not lock.acquire(timeout=5):
        return jsonify({'success': False, 'message': '获取写锁超时'}), 500

    try:
        package = packages.get(package_id)
        if package:
            package.status = data.get('status', package.status)
            package.history.append((package.status, datetime.now()))
            return jsonify({'success': True, 'message': '包裹状态更新成功'}), 200
    finally:
        lock.release()

    return jsonify({'success': False, 'message': '包裹未找到'}), 404

# 配送管理
@app.route('/delivery/assign', methods=['POST'])
def assign_delivery():
    """
    分配配送任务
    ---
    tags: [配送管理]
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [delivery_id, package_id, courier]
          properties:
            delivery_id: {type: string}
            package_id: {type: string}
            courier: {type: string}
    responses:
      201: {description: 配送任务分配成功}
      400: {description: 配送任务已存在}
    """
    data = request.get_json()
    delivery_id = data.get('delivery_id')
    package_id = data.get('package_id')
    courier = data.get('courier')

    lock = deliveries_lock.gen_wlock()
    if not lock.acquire(timeout=5):
        return jsonify({'success': False, 'message': '获取写锁超时'}), 500

    try:
        if delivery_id in deliveries:
            return jsonify({'success': False, 'message': '配送任务已存在'}), 400
        delivery = Delivery(delivery_id, package_id, courier)
        deliveries[delivery_id] = delivery
    finally:
        lock.release()

    return jsonify({'success': True, 'message': '配送任务分配成功'}), 201

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
            return jsonify({'success': True, 'delivery': {'delivery_id': delivery.delivery_id, 'package_id': delivery.package_id, 'courier': delivery.courier, 'status': delivery.status, 'history': delivery.history}}), 200
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
            delivery.status = data.get('status', delivery.status)
            delivery.history.append((delivery.status, datetime.now()))
            return jsonify({'success': True, 'message': '配送状态更新成功'}), 200
    finally:
        lock.release()

    return jsonify({'success': False, 'message': '配送任务未找到'}), 404

# 通知系统（示例）
@app.route('/notify/package/<package_id>', methods=['POST'])
def notify_package_status(package_id):
    """
    通知包裹状态
    ---
    tags: [通知系统]
    parameters:
      - in: path
        name: package_id
        required: true
        type: string
    responses:
      200: {description: 通知发送成功}
    """
    # 这里可以实现通知逻辑，例如通过短信或邮件通知用户
    return jsonify({'success': True, 'message': f'包裹 {package_id} 的通知已发送'}), 200

@app.route('/notify/delivery/<delivery_id>', methods=['POST'])
def notify_delivery_status(delivery_id):
    """
    通知配送状态
    ---
    tags: [通知系统]
    parameters:
      - in: path
        name: delivery_id
        required: true
        type: string
    responses:
      200: {description: 通知发送成功}
    """
    # 这里可以实现通知逻辑，例如通过短信或邮件通知配送员
    return jsonify({'success': True, 'message': f'配送任务 {delivery_id} 的通知已发送'}), 200

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
    app.run(host='localhost', port=5000)