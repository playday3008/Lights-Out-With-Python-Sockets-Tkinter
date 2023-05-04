def switch_cell(matrix: list[list[int]], x: int, y: int) -> None:
    matrix[x][y] += 1
    if x > 0:
        matrix[x - 1][y] += 1
    if x < len(matrix) - 1:
        matrix[x + 1][y] += 1
    if y > 0:
        matrix[x][y - 1] += 1
    if y < len(matrix[0]) - 1:
        matrix[x][y + 1] += 1

def init_coeff_matrix(x: int, y: int) -> list[list[int]]:
    matrix = [[0 for _ in range(x * y + 1)] for _ in range(x * y)]
    for i in range(x):
        for j in range(y):
            k = i * y + j
            matrix[k][k] = 1
            if i > 0:
                matrix[(i - 1) * y + j][k] = 1
            if i < x - 1:
                matrix[(i + 1) * y + j][k] = 1
            if j > 0:
                matrix[i * y + j - 1][k] = 1
            if j < y - 1:
                matrix[i * y + j + 1][k] = 1
    return matrix

def solve(matrix: list[list[int]]) -> list[list[list[int]]]:
    cells = len(matrix) * len(matrix[0])
    coeff_rank, matrix_rank = 0, 0
    coeff_matrix = init_coeff_matrix(len(matrix), len(matrix[0]))
    # Add our problem to coefficient matrix
    for i in range(len(matrix)):
        for j in range(len(matrix[i])):
            coeff_matrix[i * len(matrix[i]) + j][cells] = matrix[i][j] & 1  # Convert to binary

    # Conversion of augmented matrix to ladder matrix
    for i, y in zip(range(cells), range(cells)):
        x = i
        for j in range(i + 1, cells):
            if coeff_matrix[j][i] > coeff_matrix[x][i]:
                x = j
        if x - i:  # Exchange matrix row data
            for k in range(y, cells + 1):
                coeff_matrix[i][k] ^= coeff_matrix[x][k]
                coeff_matrix[x][k] ^= coeff_matrix[i][k]
                coeff_matrix[i][k] ^= coeff_matrix[x][k]
        if coeff_matrix[i][y] == 0:
            i -= 1
            continue
        # Elimination
        for j in range(i + 1, cells):
            if coeff_matrix[j][y]:
                for k in range(y, cells + 1):
                    coeff_matrix[j][k] ^= coeff_matrix[i][k]

    # Computation of Rank of Coefficient Matrix and Rank of Extended Matrix
    solution = []
    for i in range(cells):
        rank1, rank2 = 0, 0
        for j in range(cells + 1):
            if j < cells:
                rank1 |= coeff_matrix[i][j]
            rank2 |= coeff_matrix[i][j]
        coeff_rank += rank1
        matrix_rank += rank2

    # Enumeration and Replacement Solution
    if coeff_rank >= matrix_rank:
        temp = [0 for _ in range(cells)]
        for i in range(1 << (cells - coeff_rank), 0, -1):
            for j in range(cells - 1, coeff_rank, -1):
                coeff_matrix[j - 1][cells] += coeff_matrix[j][cells] >> 1
                coeff_matrix[j][cells] &= 1
            for j in range(cells):
                temp[j] = coeff_matrix[j][cells]
            for j in range(cells - 1, -1, -1):
                for k in range(j - 1, -1, -1):
                    if coeff_matrix[k][j]:
                        temp[k] ^= temp[j]

            temp2d = [[0 for _ in range(len(matrix[0]))] for _ in range(len(matrix))]
            for j in range(len(temp2d)):
                for k in range(len(temp2d[j])):
                    temp2d[j][k] = temp[j * len(temp2d[j]) + k]
            solution.append(temp2d)
            coeff_matrix[cells - 1][cells] += 1
    return solution


example = [[0, 1, 0], [1, 1, 1], [0, 1, 0], [0, 0, 0], [0, 0, 0]]

print(solve(example))

# Output:
out = [
    [
        [0, 0, 0],
        [0, 1, 0],
        [0, 0, 0],
        [0, 0, 0],
        [0, 0, 0],
    ],
    [
        [1, 0, 0],
        [1, 0, 0],
        [1, 0, 1],
        [0, 1, 1],
        [0, 0, 1],
    ],
    [
        [0, 1, 0],
        [1, 0, 1],
        [0, 0, 0],
        [1, 1, 1],
        [0, 1, 0],
    ],
    [
        [1, 1, 0],
        [0, 1, 1],
        [1, 0, 1],
        [1, 0, 0],
        [0, 1, 1],
    ],
    [
        [0, 0, 1],
        [0, 0, 1],
        [1, 0, 1],
        [1, 1, 0],
        [1, 0, 0],
    ],
    [
        [1, 0, 1],
        [1, 1, 1],
        [0, 0, 0],
        [1, 0, 1],
        [1, 0, 1],
    ],
    [
        [0, 1, 1],
        [1, 1, 0],
        [1, 0, 1],
        [0, 0, 1],
        [1, 1, 0],
    ],
    [
        [1, 1, 1],
        [0, 0, 0],
        [0, 0, 0],
        [0, 1, 0],
        [1, 1, 1],
    ],
]
