import numpy as np
from scipy.sparse import csr_matrix, lil_matrix
from scipy.sparse.linalg import gmres, cg, spsolve

class LinearSystem:
    """Linear system Ax = b"""
    def __init__(self, size):
        self.A = lil_matrix((size, size))
        self.b = np.zeros(size)
        self.x = np.zeros(size)
        self.size = size
    
    def set_coeff(self, i, j, value):
        """Set coefficient A[i,j]"""
        self.A[i, j] = value
    
    def set_rhs(self, i, value):
        """Set RHS b[i]"""
        self.b[i] = value
    
    def to_csr(self):
        """Convert to sparse row format"""
        return self.A.tocsr()
    
    def solve(self, method='direct'):
        """Solve Ax = b"""
        A_csr = self.to_csr()
        
        if method == 'direct':
            self.x = spsolve(A_csr, self.b)
        elif method == 'gmres':
            self.x, info = gmres(A_csr, self.b, x0=self.x, tol=1e-6, maxiter=1000)
        elif method == 'cg':
            self.x, info = cg(A_csr, self.b, x0=self.x, tol=1e-6, maxiter=1000)
        elif method == 'gauss_seidel':
            self.x = self.gauss_seidel(self.b)
        
        return self.x
    
    def gauss_seidel(self, b, max_iter=1000, tol=1e-6):
        """Gauss-Seidel iterative solver"""
        x = self.x.copy()
        A = self.A.tolil()
        
        for iteration in range(max_iter):
            x_old = x.copy()
            
            for i in range(self.size):
                sum_ax = 0
                for j in range(self.size):
                    if i != j:
                        sum_ax += A[i, j] * x[j]
                
                if abs(A[i, i]) > 1e-15:
                    x[i] = (b[i] - sum_ax) / A[i, i]
            
            residual = np.linalg.norm(x - x_old)
            if residual < tol:
                break
        
        return x

class IterativeSolver:
    """Iterative solvers for linear systems"""
    
    @staticmethod
    def jacobi(A, b, x0=None, tol=1e-6, max_iter=1000):
        """Jacobi iteration"""
        n = len(b)
        if x0 is None:
            x = np.zeros(n)
        else:
            x = x0.copy()
        
        D = np.diag(np.diag(A))
        R = A - D
        D_inv = np.linalg.inv(D)
        
        for iteration in range(max_iter):
            x_new = D_inv @ (b - R @ x)
            if np.linalg.norm(x_new - x) < tol:
                break
            x = x_new
        
        return x
    
    @staticmethod
    def gauss_seidel(A, b, x0=None, tol=1e-6, max_iter=1000):
        """Gauss-Seidel iteration"""
        n = len(b)
        if x0 is None:
            x = np.zeros(n)
        else:
            x = x0.copy()
        
        L = np.tril(A)
        U = A - L
        
        for iteration in range(max_iter):
            x_new = np.linalg.solve(L, b - U @ x)
            if np.linalg.norm(x_new - x) < tol:
                break
            x = x_new
        
        return x
    
    @staticmethod
    def sor(A, b, x0=None, omega=1.5, tol=1e-6, max_iter=1000):
        """Successive Over-Relaxation"""
        n = len(b)
        if x0 is None:
            x = np.zeros(n)
        else:
            x = x0.copy()
        
        for iteration in range(max_iter):
            x_old = x.copy()
            
            for i in range(n):
                sum_ax = 0
                for j in range(n):
                    if i != j:
                        sum_ax += A[i, j] * x[j]
                
                if abs(A[i, i]) > 1e-15:
                    x[i] = (1 - omega) * x_old[i] + (omega / A[i, i]) * (b[i] - sum_ax)
            
            if np.linalg.norm(x - x_old) < tol:
                break
        
        return x
    
    @staticmethod
    def conjugate_gradient(A, b, x0=None, tol=1e-6, max_iter=None):
        """Conjugate Gradient Method"""
        n = len(b)
        if max_iter is None:
            max_iter = n
        
        if x0 is None:
            x = np.zeros(n)
        else:
            x = x0.copy()
        
        r = b - A @ x
        p = r.copy()
        rsold = np.dot(r, r)
        
        for i in range(max_iter):
            Ap = A @ p
            alpha = rsold / (np.dot(p, Ap) + 1e-15)
            x = x + alpha * p
            r = r - alpha * Ap
            rsnew = np.dot(r, r)
            
            if np.sqrt(rsnew) < tol:
                break
            
            beta = rsnew / (rsold + 1e-15)
            p = r + beta * p
            rsold = rsnew
        
        return x
    
    @staticmethod
    def gmres(A, b, x0=None, restart=100, tol=1e-6, max_iter=1000):
        """GMRES (Generalized Minimal Residual)"""
        A_csr = csr_matrix(A)
        if x0 is None:
            x0 = np.zeros(len(b))
        
        x, info = gmres(A_csr, b, x0=x0, restart=restart, tol=tol, maxiter=max_iter)
        return x

class Preconditioner:
    """Preconditioners for iterative solvers"""
    
    @staticmethod
    def diagonal(A):
        """Diagonal preconditioner (Jacobi)"""
        return np.diag(1 / (np.diag(A) + 1e-15))
    
    @staticmethod
    def ILU(A, drop_tol=0.01):
        """Incomplete LU factorization"""
        n = A.shape[0]
        L = np.zeros_like(A)
        U = np.zeros_like(A)
        
        for k in range(n):
            for i in range(k, n):
                sum_lu = 0
                for j in range(k):
                    sum_lu += L[i, j] * U[j, k]
                U[i, k] = A[i, k] - sum_lu
            
            for i in range(k+1, n):
                sum_lu = 0
                for j in range(k):
                    sum_lu += L[i, j] * U[j, k]
                L[i, k] = (A[i, k] - sum_lu) / (U[k, k] + 1e-15)
        
        return L, U
    
    @staticmethod
    def DILU(A):
        """Diagonal Incomplete LU"""
        return Preconditioner.diagonal(A)
    
    @staticmethod
    def apply_preconditioner(P, r):
        """Apply preconditioner to residual"""
        return P @ r
