import numpy as np
import matplotlib.pyplot as plt
from sklearn.cluster import KMeans, AgglomerativeClustering, DBSCAN
import networkx as nx
import time
import itertools
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp

# 生成随机经纬度坐标点
def generate_random_coordinates(n, lat_range=(0, 10000), lon_range=(0, 10000)):
    lats = np.random.uniform(lat_range[0], lat_range[1], n)
    lons = np.random.uniform(lon_range[0], lon_range[1], n)
    return np.column_stack((lats, lons))

# K-means聚类
def solve_tsp_dynamic_programming(distance_matrix):
    """使用动态规划(Held-Karp算法)解决TSP问题。"""
    keys = list(distance_matrix.keys())
    n = len(keys)
    print(n)
    # 检查输入的距离矩阵是否有效
    if n == 0 or any(len(distance_matrix[key]) != n for key in distance_matrix):
        raise ValueError("距离矩阵无效，确保是一个方形矩阵。")

    C = {}
    for k in range(1, n):
        C[(1 << k, k)] = (distance_matrix[keys[0]][keys[k]], 0)

    # 动态规划计算每个子集的最小路径
    for subset_size in range(2, n):
        for subset in itertools.combinations(range(1, n), subset_size):
            bits = sum(1 << bit for bit in subset)  # 计算位掩码
            for k in subset:
                prev_bits = bits & ~(1 << k)
                res = []
                for m in subset:
                    if m == 0 or m == k:
                        continue
                    res.append((C[(prev_bits, m)][0] + distance_matrix[keys[m]][keys[k]], m))
                C[(bits, k)] = min(res, default=(float('inf'), None))  # 默认值处理

    bits = (1 << n) - 2  # 计算全遍历的位掩码
    res = []
    for k in range(1, n):
        res.append((C.get((bits, k), (float('inf'), None))[0] + distance_matrix[keys[k]][keys[0]], k))
    
    opt, parent = min(res, default=(float('inf'), None))
    if parent is None:
        return float('inf'), []  # 如果找不到路径，返回无穷大和空路径

    path = []
    for _ in range(n - 1):
        path.append(keys[parent])
        bits, parent = bits & ~(1 << parent), C.get((bits, parent), (None, None))[1]
    path.append(keys[0])
    path.reverse()
    
    return opt, path

# 示例用法
distance_matrix = {
    0: {0: 0,1: 10, 2: 15, 3: 20},
    1: {0: 10,1:0, 2: 35, 3: 25},
    2: {0: 15, 1: 35,2:0, 3: 30},
    3: {0: 20, 1: 25, 2: 30,3:0}
}

opt, path = solve_tsp_dynamic_programming(distance_matrix)
print(f"最短路径长度: {opt}")
print(f"最优路径: {path}")


def solve_tsp_networkx(distance_matrix):
    """Solves the TSP problem using networkx."""
    G = create_graph(distance_matrix)
    tsp_path = nx.approximation.traveling_salesman_problem(G, cycle=True)
    # 计算路径长度
    tsp_length = sum(distance_matrix[u][v] for u, v in zip(tsp_path, tsp_path[1:] + [tsp_path[0]]))
    return tsp_length, tsp_path

def solve_tsp_dynamic_programming(distance_matrix):
    """使用动态规划（Held-Karp算法）解决TSP问题。"""
    keys = list(distance_matrix.keys())
    n = len(keys)
    
    # 检查输入的距离矩阵是否有效
    if n == 0 or any(len(distance_matrix[key]) != n for key in distance_matrix):
        raise ValueError("距离矩阵无效，确保是一个方形矩阵。")

    C = {}
    for k in range(1, n):
        C[(1 << k, k)] = (distance_matrix[keys[0]][keys[k]], 0)

    # 动态规划计算每个子集的最小路径
    for subset_size in range(2, n):
        for subset in itertools.combinations(range(1, n), subset_size):
            bits = sum(1 << bit for bit in subset)  # 计算位掩码
            for k in subset:
                prev_bits = bits & ~(1 << k)
                res = []
                for m in subset:
                    if m == 0 or m == k:
                        continue
                    res.append((C[(prev_bits, m)][0] + distance_matrix[keys[m]][keys[k]], m))
                C[(bits, k)] = min(res, default=(float('inf'), None))  # 默认值处理

    bits = (1 << n) - 2  # 计算全遍历的位掩码
    res = []
    for k in range(1, n):
        res.append((C.get((bits, k), (float('inf'), None))[0] + distance_matrix[keys[k]][keys[0]], k))
    
    opt, parent = min(res, default=(float('inf'), None))
    if parent is None:
        return float('inf'), []  # 如果找不到路径，返回无穷大和空路径

    path = []
    for _ in range(n - 1):
        path.append(keys[parent])
        bits, parent = bits & ~(1 << parent), C.get((bits, parent), (None, None))[1]
    path.append(keys[0])
    path.reverse()
    
    return opt, path

def calculate_distance_matrix(coordinates_dict):
    """Calculates the distance matrix for the given coordinates."""
    keys = list(coordinates_dict.keys())
    n = len(keys)
    distance_matrix = {}
    
    for i in range(n):
        for j in range(i + 1, n):
            key_i, key_j = keys[i], keys[j]
            distance = np.linalg.norm(coordinates_dict[key_i] - coordinates_dict[key_j])
            if key_i not in distance_matrix:
                distance_matrix[key_i] = {}
            if key_j not in distance_matrix:
                distance_matrix[key_j] = {}
            distance_matrix[key_i][key_j] = distance
            distance_matrix[key_j][key_i] = distance
    
    return distance_matrix
