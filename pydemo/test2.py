
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Button
from sklearn.cluster import KMeans, AgglomerativeClustering,DBSCAN
import networkx as nx
import time
import itertools
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp


# hierarchical聚类

def hierarchical_clustering(coordinates, n_clusters):
    hierarchical = AgglomerativeClustering(n_clusters=n_clusters)
    labels = hierarchical.fit_predict(coordinates)
    cluster_centers = np.array([coordinates[labels == i].mean(axis=0) for i in range(n_clusters)])
    return labels, cluster_centers

def create_graph(distance_matrix):
    """Creates a graph from the distance matrix."""
    G = nx.Graph()
    for u in distance_matrix:
        for v in distance_matrix[u]:
            G.add_edge(u, v, weight=distance_matrix[u][v])
    return G

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

def solve_tsp_or_tools(distance_matrix,time_limit=0):
    """Solves the TSP problem using Google OR-Tools."""
    # 获取原始节点标号
    original_nodes = list(distance_matrix.keys())
    num_nodes = len(original_nodes)
    ratio = 1000000#放大系数 ,因为or-tools只支持整数

    manager = pywrapcp.RoutingIndexManager(num_nodes, 1, 0)
    manager.num_search_workers = 16
    routing = pywrapcp.RoutingModel(manager)
    distance_callback = create_distance_callback(distance_matrix, manager,ratio,original_nodes)
    transit_callback_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC)
    #search_parameters.local_search_metaheuristic = (
    #    routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH)
    search_parameters.use_cp_sat=True
    if time_limit > 0:
        search_parameters.time_limit.seconds = int(time_limit)
        search_parameters.time_limit.nanos = int((time_limit-int(time_limit))*1000000000)
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
def GET_task_path(coordinates):
    coordinates = np.array(coordinates)
    # 计算距离矩阵
    distance_matrix = calculate_distance_matrix_list(coordinates)    

    def get_result_dpot(tsp_path_dp):
        start_time = time.time()
        total_path_dpot = []
        clusters_path = []
        for index, cluster in enumerate(tsp_path_dp):
            cluster_points = clusters[cluster]
            print(cluster_points)
            # 检查聚类中的点数
            if len(cluster_points) == 0:
                continue  # 跳过没有点的聚类
            elif len(cluster_points) == 1:
                tsp_path = [list(cluster_points.keys())[0]]  # 只有一个点，路径就是该点本身
            else:
                cluster_distance_matrix = calculate_distance_matrix_map(cluster_points)
                tsp_path = solve_tsp_or_tools(cluster_distance_matrix)
            
            if total_path_dpot and len(tsp_path) > 1:
                last_point = total_path_dpot[-1]
                min_distance = float('inf')
                min_index = 0
                for i, point in enumerate(tsp_path):
                    distance = distance_matrix[last_point][point]
                    if distance < min_distance:
                        min_distance = distance
                        min_index = i
                tsp_path = tsp_path[min_index:] + tsp_path[:min_index]
            
            clusters_path.append(tsp_path)
            total_path_dpot += tsp_path
        
        end_time = time.time()
        clusters_length = [float(sum(distance_matrix[path[i]][path[i + 1]] for i in range(len(path) - 1))) for path in clusters_path]
        return total_path_dpot, end_time - start_time, clusters_path, clusters_length
    
    
    if len(coordinates) <100:
        ortools_path=solve_tsp_or_tools({index: value for index, value in enumerate(distance_matrix)},10)
        #print(ortools_path)
        ortools_length=sum(distance_matrix[ortools_path[i]][ortools_path[i + 1]] for i in range(0,len(ortools_path)-1))
        return ortools_path,ortools_length,[],[]


    n_clusters=min(2,len(coordinates))
    labels, cluster_centers = hierarchical_clustering(coordinates, n_clusters)
    
    # 获取每个聚类的点集
    clusters = {}
    for cluster_id in range(n_clusters):
        clusters[cluster_id] = {index: coordinates[index] for index in range(len(coordinates)) if labels[index] == cluster_id}
    # 计算聚类中心之间的距离矩阵
    cluster_distance_matrix = calculate_distance_matrix_list(cluster_centers)
    # 使用动态规划解决聚类中心的 TSP 问题
    
    tsp_length_dp, tsp_path_dp = solve_tsp_dynamic_programming(cluster_distance_matrix)

    total_path_dpot,dpot_time,clusters_path,clusters_length=get_result_dpot(tsp_path_dp)

    total_length_dpot=sum(distance_matrix[total_path_dpot[i]][total_path_dpot[i + 1]] for i in range(0,len(total_path_dpot)-1))    
    return total_path_dpot,total_length_dpot,clusters_path,clusters_length
