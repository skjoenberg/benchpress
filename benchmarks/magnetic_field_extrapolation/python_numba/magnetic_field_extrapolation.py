# This Python file uses the following encoding: utf-8
from benchpress import util
import numpy as np
from math import cos, sin, exp, pi
import numba
from numba import cuda

def window(B,a=0.37):
    assert (len(B.shape) == 2)
    assert (B.shape[0] == B.shape[1])
    n = B.shape[0]
    wl = np.ones_like(B[0])
    b = int(np.ceil((a * (n-1) / 2)))
    wl[:b]  =  0.5 * (1 + np.cos(pi*(2 * np.arange(b) / (a * (n-1)) - 1)))
    wl[-b:] =  0.5 * (1 + np.cos(pi*(2 * np.arange(b-1,-1,-1) / (a * (n-1)) - 1)))
    wl *= wl
    w = np.sqrt(wl+wl[:,None])
    return B*w

def calcB_loop(B_x0, alpha=0.0,
          x_min = 0.0, x_max = 0.25,
          y_min = 0.0, y_max = 1.0,
          z_min = 0.0, z_max = 1.0):

    n = len(B_x0)

    x = np.linspace(x_min,x_max,num=n,endpoint=False).astype(B_x0.dtype,copy=False)
    y = np.linspace(y_min,y_max,num=n).astype(B_x0.dtype,copy=False)
    z = np.linspace(z_min,z_max,num=n).astype(B_x0.dtype,copy=False)
    u = np.arange(n,dtype=B_x0.dtype)

    # Making C
    C = 4.0 / (n-1.0)**2 * np.sum(np.sum((B_x0 * np.sin(pi/y_max * u * y[:,None])[:,:,None])[:,None] * np.sin(pi/z_max * u * z[:,None])[:,None],-1),-1)
    l = np.pi**2 * ((u**2 / y_max)[:,None] + (u**2 / z_max))
    l[0,0] = 1.0
    r = np.sqrt(l - alpha**2)

    # Calculating B
    Bx = np.empty((n,n,n),dtype=B_x0.dtype)
    By = np.empty((n,n,n),dtype=B_x0.dtype)
    Bz = np.empty((n,n,n),dtype=B_x0.dtype)
    for i in range(n):
        for j in range(n):
            Bx[:, i, j] = 0
            By[:, i, j] = 0
            Bz[:, i, j] = 0
            temp_x = np.empty((n, n), dtype=B_x0.dtype)
            temp_y = np.empty((n, n), dtype=B_x0.dtype)
            temp_z = np.empty((n, n), dtype=B_x0.dtype)
            for k in range(n):
                for m in range(n):
                    sincos = np.sin(np.pi * u[k] * y[i] / y_max) * (u[m] * np.cos(np.pi * u[m] * z[j] / z_max))
                    cossin = (u[k] * np.cos(np.pi * u[k] * y[i] / y_max)) * (np.sin(np.pi * u[m] * z[j] / z_max))
                    temp_x[k,m] = C[k,m] * (np.sin(np.pi * u[k] * y[i] / y_max) * (np.sin(np.pi * u[m] * z[j] / z_max)))
                    temp_y[k,m] = C[k,m] / l[k,m] * (alpha * np.pi / z_max * sincos - r[k,m] * np.pi / y_max * cossin)
                    temp_z[k,m] = C[k,m] / l[k,m] * (alpha * np.pi / y_max * cossin + r[k,m] * np.pi / z_max * sincos)
            for k in range(n):
                for m in range(n):
                    for q in range(n):
                        exprx = np.exp(-r[m, q] * x[k])
                        Bx[k, i, j] += temp_x[m, q] * exprx
                        By[k, i, j] += temp_y[m, q] * exprx
                        Bz[k, i, j] += temp_z[m, q] * exprx
    return (Bx, By, Bz)


#@cuda.jit()
@numba.jit(nopython=True)
def loop(n, Bx, By, Bz, u, y, y_max, z, z_max, alpha, C, l, r, x, temp_x, temp_y, temp_z):
    for i in range(n):
        for j in range(n):
            Bx[:, i, j] = 0
            By[:, i, j] = 0
            Bz[:, i, j] = 0
            for k in range(n):
                for m in range(n):
                    sincos = sin(np.pi * u[k] * y[i] / y_max) * (u[m] * cos(np.pi * u[m] * z[j] / z_max))
                    cossin = (u[k] * cos(np.pi * u[k] * y[i] / y_max)) * (sin(np.pi * u[m] * z[j] / z_max))
                    temp_x[k,m] = C[k,m] * (sin(np.pi * u[k] * y[i] / y_max) * (sin(np.pi * u[m] * z[j] / z_max)))
                    temp_y[k,m] = C[k,m] / l[k,m] * (alpha * np.pi / z_max * sincos - r[k,m] * np.pi / y_max * cossin)
                    temp_z[k,m] = C[k,m] / l[k,m] * (alpha * np.pi / y_max * cossin + r[k,m] * np.pi / z_max * sincos)
            for k in range(n):
                for m in range(n):
                    for q in range(n):
                        exprx = exp(-r[m, q] * x[k])
                        Bx[k, i, j] += temp_x[m, q] * exprx
                        By[k, i, j] += temp_y[m, q] * exprx
                        Bz[k, i, j] += temp_z[m, q] * exprx


def calcB_numba(B_x0, alpha=0.0,
          x_min = 0.0, x_max = 0.25,
          y_min = 0.0, y_max = 1.0,
          z_min = 0.0, z_max = 1.0):

    n = len(B_x0)

    x = np.linspace(x_min,x_max,num=n,endpoint=False).astype(B_x0.dtype,copy=False)
    y = np.linspace(y_min,y_max,num=n).astype(B_x0.dtype,copy=False)
    z = np.linspace(z_min,z_max,num=n).astype(B_x0.dtype,copy=False)
    u = np.arange(n,dtype=B_x0.dtype)

    # Making C
    C = 4.0 / (n-1.0)**2 * np.sum(np.sum((B_x0 * np.sin(pi/y_max * u * y[:,None])[:,:,None])[:,None] * np.sin(pi/z_max * u * z[:,None])[:,None],-1),-1)
    l = np.pi**2 * ((u**2 / y_max)[:,None] + (u**2 / z_max))
    l[0,0] = 1.0
    r = np.sqrt(l - alpha**2)

    # Calculating B
    Bx = np.empty((n,n,n),dtype=B_x0.dtype)
    By = np.empty((n,n,n),dtype=B_x0.dtype)
    Bz = np.empty((n,n,n),dtype=B_x0.dtype)
    temp_x = np.empty((n, n), dtype=B_x0.dtype)
    temp_y = np.empty((n, n), dtype=B_x0.dtype)
    temp_z = np.empty((n, n), dtype=B_x0.dtype)
    loop(n, Bx, By, Bz, u, y, y_max, z, z_max, alpha, C, l, r, x, temp_x, temp_y, temp_z)
    return (Bx, By, Bz)


def main():
    B = util.Benchmark()
    if B.inputfn is None:
        B_x0 = B.random_array((B.size[0],B.size[1]), dtype=B.dtype)
    else:
        inputfn = B.inputfn if B.inputfn else '../idl_input-float64_512*512.npz'
        sd = { 512:1, 256:2, 128:4, 64:8, 32:16, 16:32, 8:64}
        try:
            h = sd[B.size[0]]
            w = sd[B.size[1]]
        except KeyError:
            raise ValueError('Only valid sizes are: '+str(sd.keys()))
        B_x0 = B.load_array(inputfn, 'input', dtype=B.dtype)[::h,::w]

    B.start()
    for _ in range(B.size[2]):
        Rx, Ry, Rz = calcB_numba(window(B_x0.copy()))
    B.stop()
    B.pprint()

    if B.outputfn:
        R = Rx+Ry+Rz
        B.tofile(B.outputfn, {'res': R, 'res_x': Rx, 'res_y': Ry, 'res_z': Rz})

if __name__ == '__main__':
    main()
