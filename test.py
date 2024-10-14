import networkx as nx
import random
import time
from deap import base, creator, tools, algorithms
import itertools

def create_graph(distance_matrix):
    """Creates a graph from the distance matrix."""
    G = nx.Graph()
    n = len(distance_matrix)
    for i in range(n):
        for j in range(n):
            if i != j:
                G.add_edge(i, j, weight=distance_matrix[i][j])
    return G

def solve_tsp_networkx(distance_matrix):
    """Solves the TSP problem using networkx."""
    G = create_graph(distance_matrix)
    tsp_path = nx.approximation.traveling_salesman_problem(G, cycle=True)
    # 计算路径长度
    tsp_length = sum(distance_matrix[u][v] for u, v in zip(tsp_path, tsp_path[1:] + [tsp_path[0]]))
    return tsp_length, tsp_path

def generate_random_distance_matrix(n, max_distance=100000):
    """Generates a random distance matrix for n nodes."""
    distance_matrix = [[0 if i == j else random.randint(1, max_distance) for j in range(n)] for i in range(n)]
    # Make the matrix symmetric
    for i in range(n):
        for j in range(i + 1, n):
            distance_matrix[j][i] = distance_matrix[i][j]
    return distance_matrix

def solve_tsp_genetic(distance_matrix, population_size=500, generations=100, mutation_prob=0.3, crossover_prob=0.7):
    """Solves the TSP problem using a genetic algorithm."""
    n = len(distance_matrix)
    
    # Define the evaluation function
    def eval_tsp(individual):
        return sum(distance_matrix[individual[i]][individual[i + 1]] for i in range(n - 1)) + distance_matrix[individual[-1]][individual[0]],

    # Create the toolbox
    creator.create("FitnessMin", base.Fitness, weights=(-1.0,))
    creator.create("Individual", list, fitness=creator.FitnessMin)
    toolbox = base.Toolbox()
    toolbox.register("indices", random.sample, range(n), n)
    toolbox.register("individual", tools.initIterate, creator.Individual, toolbox.indices)
    toolbox.register("population", tools.initRepeat, list, toolbox.individual)
    toolbox.register("mate", tools.cxOrdered)
    toolbox.register("mutate", tools.mutShuffleIndexes, indpb=0.05)
    toolbox.register("select", tools.selTournament, tournsize=3)
    toolbox.register("evaluate", eval_tsp)

    # Create the population
    population = toolbox.population(n=population_size)

    # Apply the genetic algorithm
    algorithms.eaSimple(population, toolbox, cxpb=crossover_prob, mutpb=mutation_prob, ngen=generations, verbose=False)

    # Get the best individual
    best_individual = tools.selBest(population, 1)[0]
    best_length = eval_tsp(best_individual)[0]
    return best_length, best_individual

def solve_tsp_dynamic_programming(distance_matrix):
    """Solves the TSP problem using dynamic programming (Held-Karp algorithm)."""
    n = len(distance_matrix)
    C = {}
    for k in range(1, n):
        C[(1 << k, k)] = (distance_matrix[0][k], 0)
    for subset_size in range(2, n):
        for subset in itertools.combinations(range(1, n), subset_size):
            bits = 0
            for bit in subset:
                bits |= 1 << bit
            for k in subset:
                prev_bits = bits & ~(1 << k)
                res = []
                for m in subset:
                    if m == 0 or m == k:
                        continue
                    res.append((C[(prev_bits, m)][0] + distance_matrix[m][k], m))
                C[(bits, k)] = min(res)
    bits = (2**n - 1) - 1
    res = []
    for k in range(1, n):
        res.append((C[(bits, k)][0] + distance_matrix[k][0], k))
    opt, parent = min(res)
    path = []
    for i in range(n - 1):
        path.append(parent)
        bits, parent = bits & ~(1 << parent), C[(bits, parent)][1]
    path.append(0)
    path.reverse()
    return opt, path

# 生成包含 10 个节点的随机距离矩阵
n = 20
distance_matrix = generate_random_distance_matrix(n)

# 使用 networkx 解决 TSP 问题
start_time = time.time()
tsp_length_nx, tsp_path_nx = solve_tsp_networkx(distance_matrix)
end_time = time.time()
elapsed_time_nx = end_time - start_time

# 使用遗传算法解决 TSP 问题
start_time = time.time()
tsp_length_ga, tsp_path_ga = solve_tsp_genetic(distance_matrix)
end_time = time.time()
elapsed_time_ga = end_time - start_time

# 使用动态规划算法解决 TSP 问题
start_time = time.time()
tsp_length_dp, tsp_path_dp = solve_tsp_dynamic_programming(distance_matrix)
end_time = time.time()
elapsed_time_dp = end_time - start_time

# 输出结果
print(f"NetworkX 最短路径长度: {tsp_length_nx}")
print(f"NetworkX 最优路径: {tsp_path_nx}")
print(f"NetworkX 运行时间: {elapsed_time_nx:.2f} 秒")

print(f"遗传算法 最短路径长度: {tsp_length_ga}")
print(f"遗传算法 最优路径: {tsp_path_ga}")
print(f"遗传算法 运行时间: {elapsed_time_ga:.2f} 秒")

print(f"动态规划算法 最短路径长度: {tsp_length_dp}")
print(f"动态规划算法 最优路径: {tsp_path_dp}")
print(f"动态规划算法 运行时间: {elapsed_time_dp:.2f} 秒")