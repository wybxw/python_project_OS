import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Button
from sklearn.cluster import KMeans, AgglomerativeClustering,DBSCAN
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

#K-means聚类
def kmeans_clustering(coordinates, n_clusters):
    kmeans = KMeans(n_clusters=n_clusters,random_state=42)
    kmeans.fit(coordinates)
    labels = kmeans.labels_
    cluster_centers = kmeans.cluster_centers_
    return labels, cluster_centers
# hierarchical聚类

def hierarchical_clustering(coordinates, n_clusters):
    hierarchical = AgglomerativeClustering(n_clusters=n_clusters)
    labels = hierarchical.fit_predict(coordinates)
    cluster_centers = np.array([coordinates[labels == i].mean(axis=0) for i in range(n_clusters)])
    return labels, cluster_centers
# 可视化聚类结果

def create_graph(distance_matrix):
    """Creates a graph from the distance matrix."""
    G = nx.Graph()
    for u in distance_matrix:
        for v in distance_matrix[u]:
            G.add_edge(u, v, weight=distance_matrix[u][v])
    return G

# def solve_tsp_networkx(distance_matrix):
#     """Solves the TSP problem using networkx."""
#     G = create_graph(distance_matrix)
#     tsp_path = nx.approximation.traveling_salesman_problem(G, cycle=True)
#     # 计算路径长度
#     tsp_length = sum(distance_matrix[u][v] for u, v in zip(tsp_path, tsp_path[1:] + [tsp_path[0]]))
#     return tsp_length, tsp_path
def solve_tsp_networkx(distance_matrix):
    G = create_graph(distance_matrix)
    tsp_path = nx.approximation.traveling_salesman_problem(G, cycle=False)
    return tsp_path

def solve_tsp_dynamic_programming(distance_matrix):
    """使用动态规划(Held-Karp算法)解决TSP问题。"""
    n = len(distance_matrix)
    
    # 检查输入的距离矩阵是否有效
    if n == 0 or any(len(row) != n for row in distance_matrix):
        raise ValueError("距离矩阵无效，确保是一个方形矩阵。")

    C = {}
    for k in range(1, n):
        C[(1 << k, k)] = (distance_matrix[0][k], 0)

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
                    res.append((C[(prev_bits, m)][0] + distance_matrix[m][k], m))
                C[(bits, k)] = min(res, default=(float('inf'), None))  # 默认值处理

    bits = (1 << n) - 2  # 计算全遍历的位掩码
    res = []
    for k in range(1, n):
        res.append((C.get((bits, k), (float('inf'), None))[0] + distance_matrix[k][0], k))
    
    opt, parent = min(res, default=(float('inf'), None))
    if parent is None:
        return float('inf'), []  # 如果找不到路径，返回无穷大和空路径

    path = []
    for _ in range(n - 1):
        path.append(parent)
        bits, parent = bits & ~(1 << parent), C.get((bits, parent), (None, None))[1]
    path.append(0)
    path.reverse()
    
    return opt, path

def calculate_distance_matrix_list(coordinates):
    """Calculates the distance matrix for the given coordinates."""
    n = len(coordinates)
    distance_matrix = np.zeros((n, n))
    for i in range(n):
        for j in range(i + 1, n):
            distance = np.linalg.norm(coordinates[i] - coordinates[j])
            distance_matrix[i][j] = distance
            distance_matrix[j][i] = distance
    return distance_matrix

def calculate_distance_matrix_map(coordinates_dict):
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

def find_min_distance_between_clusters(cluster1_points, cluster2_points):
    """Finds the minimum distance between two clusters."""
    min_distance = float('inf')
    for point1 in cluster1_points:
        for point2 in cluster2_points:
            distance = np.linalg.norm(point1 - point2)
            if distance < min_distance:
                min_distance = distance
    return min_distance

def create_distance_callback(distance_matrix, manager,ratio,original_nodes):
    """Creates a callback to return the distance between nodes."""
    def distance_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return int(ratio)*int(distance_matrix[original_nodes[from_node]][original_nodes[to_node]])
    return distance_callback

def solve_tsp_or_tools(distance_matrix):
    """Solves the TSP problem using Google OR-Tools."""
    # 获取原始节点标号
    original_nodes = list(distance_matrix.keys())
    num_nodes = len(original_nodes)
    ratio = 1000000#放大系数 ,因为or-tools只支持整数

    manager = pywrapcp.RoutingIndexManager(num_nodes, 1, 0)
    routing = pywrapcp.RoutingModel(manager)
    distance_callback = create_distance_callback(distance_matrix, manager,ratio,original_nodes)
    transit_callback_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC)
    solution = routing.SolveWithParameters(search_parameters)
    
    # Get the solution path and length.
    if solution:
        index = routing.Start(0)
        tsp_path = []
        while not routing.IsEnd(index):
            tsp_path.append(manager.IndexToNode(index))  # 直接使用转换后的标号
            index = solution.Value(routing.NextVar(index))
        #tsp_path.append(original_nodes[manager.IndexToNode(index)])
    else:
        return None, None
    tsp_path=list(map(lambda x:original_nodes[x],tsp_path))
    return tsp_path
def plot_paths(coordinates, path1, path2):
    fig, ax = plt.subplots(figsize=(12, 6))
    plt.subplots_adjust(bottom=0.2)

    # 提取路径1的坐标
    path1_coords = [coordinates[node] for node in path1]
    path1_x, path1_y = zip(*path1_coords)

    # 提取路径2的坐标
    path2_coords = [coordinates[node] for node in path2]
    path2_x, path2_y = zip(*path2_coords)

    # 绘制路径1
    line1, = ax.plot(path1_x, path1_y, 'o-', label='Path 1 (NetworkX)', color='blue')
    start1, = ax.plot(path1_x[0], path1_y[0], 'go', label='Start (Path 1)')
    end1, = ax.plot(path1_x[-1], path1_y[-1], 'ro', label='End (Path 1)')

    # 绘制路径2
    line2, = ax.plot(path2_x, path2_y, 's-', label='Path 2 (OR-Tools)', color='red')
    start2, = ax.plot(path2_x[0], path2_y[0], 'go', label='Start (Path 2)')
    end2, = ax.plot(path2_x[-1], path2_y[-1], 'ro', label='End (Path 2)')

    # 初始状态下隐藏路径2
    line2.set_visible(False)
    start2.set_visible(False)
    end2.set_visible(False)

    plt.title('Paths Comparison')
    plt.xlabel('Longitude')
    plt.ylabel('Latitude')
    plt.legend()
    plt.grid(True)

    # 按钮回调函数
    def show_path1(event):
        line1.set_visible(True)
        start1.set_visible(True)
        end1.set_visible(True)
        line2.set_visible(False)
        start2.set_visible(False)
        end2.set_visible(False)
        plt.draw()

    def show_path2(event):
        line1.set_visible(False)
        start1.set_visible(False)
        end1.set_visible(False)
        line2.set_visible(True)
        start2.set_visible(True)
        end2.set_visible(True)
        plt.draw()

    # 创建按钮
    ax_button1 = plt.axes([0.1, 0.05, 0.35, 0.075])
    btn1 = Button(ax_button1, 'Show Path 1')
    btn1.on_clicked(show_path1)

    ax_button2 = plt.axes([0.55, 0.05, 0.35, 0.075])
    btn2 = Button(ax_button2, 'Show Path 2')
    btn2.on_clicked(show_path2)

    plt.show()

# 主函数
if __name__ == "__main__":
    # 生成包含 100 个节点的随机经纬度坐标点
    n = 1000
    coordinates = generate_random_coordinates(n)
    # 计算距离矩阵
    distance_matrix = calculate_distance_matrix_list(coordinates)    
    # 对每个聚类内部使用 networkx 的 TSP 算法
    def get_result_dpnx(tsp_path_dp):
        start_time = time.time()
        total_path_dpnx = []
        for index, cluster in enumerate(tsp_path_dp):
            cluster_points = clusters[cluster]
            cluster_distance_matrix = calculate_distance_matrix_map(cluster_points)
            tsp_path = solve_tsp_networkx(cluster_distance_matrix)

            if total_path_dpnx:
                last_point = total_path_dpnx[-1]
                min_distance = float('inf')
                min_index = 0
                for i, point in enumerate(tsp_path):
                    distance = distance_matrix[last_point][point]
                    if distance < min_distance:
                        min_distance = distance
                        min_index = i
                tsp_path = tsp_path[min_index:] + tsp_path[:min_index]
            print(tsp_path)
            total_path_dpnx += tsp_path
        end_time = time.time()
        return total_path_dpnx,end_time-start_time
    
    
    
    
    def get_result_dpot(tsp_path_dp):
        start_time = time.time()
        total_path_dpot = []
        for index, cluster in enumerate(tsp_path_dp):
            cluster_points = clusters[cluster]
            cluster_distance_matrix = calculate_distance_matrix_map(cluster_points)
            tsp_path = solve_tsp_or_tools(cluster_distance_matrix)

            if total_path_dpot:
                last_point = total_path_dpnx[-1]
                min_distance = float('inf')
                min_index = 0
                for i, point in enumerate(tsp_path):
                    distance = distance_matrix[last_point][point]
                    if distance < min_distance:
                        min_distance = distance
                        min_index = i
                tsp_path = tsp_path[min_index:] + tsp_path[:min_index]
            print(tsp_path)
            total_path_dpot += tsp_path
        end_time = time.time()
        return total_path_dpot,end_time-start_time
    
    
    n_clusters_list = []
    kmeans_times = []
    dpnx_times = []
    dpot_times = []
    dpnx_lengths = []
    dpot_lengths = []
    for n_clusters in range(10,15):
        start_time = time.time()
        labels, cluster_centers = hierarchical_clustering(coordinates, n_clusters)
        
        # 获取每个聚类的点集
        # 获取每个聚类的点集
        clusters = {}
        for cluster_id in range(n_clusters):
            clusters[cluster_id] = {index: coordinates[index] for index in range(len(coordinates)) if labels[index] == cluster_id}

        # 计算聚类中心之间的距离矩阵
        cluster_distance_matrix = calculate_distance_matrix_list(cluster_centers)

        # 使用动态规划解决聚类中心的 TSP 问题
        
        tsp_length_dp, tsp_path_dp = solve_tsp_dynamic_programming(cluster_distance_matrix)
        end_time = time.time()
        
        kmeans_time=end_time-start_time
        print(f"聚类方式: hierarchical")
        print(f"聚类数量: {n_clusters}")
        print(f"聚类时间与动态规划耗时: {kmeans_time}")
    
        total_path_dpnx,dpnx_time=get_result_dpnx(tsp_path_dp)
        total_path_dpot,dpot_time=get_result_dpot(tsp_path_dp)
        print(total_path_dpnx)
        print(total_path_dpot)
        #根据total_path来计算total_length
        total_length_dpnx=sum(distance_matrix[total_path_dpnx[i]][total_path_dpnx[i + 1]] for i in range(0,n-1))
        total_length_dpot=sum(distance_matrix[total_path_dpot[i]][total_path_dpot[i + 1]] for i in range(0,n-1))
        print(f"聚类和动态规划+NetworkX 最短路径长度: {total_length_dpnx}")
        print(f"聚类和动态规划+NetworkX 最优路径: {total_path_dpnx}")
        print(f"聚类和动态规划+NetworkX 运行时间: {dpnx_time+kmeans_time:.5f} 秒")
        
        print(f"聚类和动态规划+OR-tools 最短路径长度: {total_length_dpot}")
        print(f"聚类和动态规划+OR-tools 最优路径: {total_path_dpot}")
        print(f"聚类和动态规划+OR-tools 运行时间: {dpot_time+kmeans_time:.5f} 秒")
        
        n_clusters_list.append(n_clusters)
        kmeans_times.append(kmeans_time)
        dpnx_times.append(dpnx_time + kmeans_time)
        dpot_times.append(dpot_time + kmeans_time)
        dpnx_lengths.append(total_length_dpnx)  # 保存NetworkX的最短路径长度
        dpot_lengths.append(total_length_dpot)   # 保存OR-tools的最短路径长度
    #设置支持中文的字体
    plt.rcParams['font.sans-serif'] = ['SimHei']  # 选择黑体
    plt.rcParams['axes.unicode_minus'] = False  # 解决负号乱码的问题
    plt.figure(figsize=(12, 8))
    #plot_paths(coordinates, total_path_dpnx, total_path_dpot)

    #绘制运行时间的折线
    plt.subplot(2, 1, 1)
    plt.plot(n_clusters_list, kmeans_times, marker='o', label='K-means耗时')
    plt.plot(n_clusters_list, dpnx_times, marker='o', label='动态规划+NetworkX耗时')
    plt.plot(n_clusters_list, dpot_times, marker='o', label='动态规划+OR-tools耗时')
    plt.title('不同聚类数下的运行时间')
    plt.xlabel('聚类数量')
    plt.ylabel('运行时间 (秒)')
    plt.xticks(n_clusters_list)  # 设置x轴刻度
    plt.legend()
    plt.grid(True)

    # 绘制最短路径长度的折线
    plt.subplot(2, 1, 2)
    plt.plot(n_clusters_list, dpnx_lengths, marker='o', label='动态规划+NetworkX最短路径长度')
    plt.plot(n_clusters_list, dpot_lengths, marker='o', label='动态规划+OR-tools最短路径长度')
    plt.title('不同聚类数下的最短路径长度')
    plt.xlabel('聚类数量')
    plt.ylabel('最短路径长度')
    plt.xticks(n_clusters_list)  # 设置x轴刻度
    plt.legend()
    plt.grid(True)

    #绘制两种路径的路线图
    plt.figure(figsize=(12, 6))
    plt.tight_layout()  # 自动调整子图参数
    plt.show()

        
        
    
    
    
    
    
    