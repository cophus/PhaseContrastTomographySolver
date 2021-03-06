"""
Complex operators computation for Torch

Michael Chen   mchen0405@berkeley.edu
David Ren      david.ren@berkeley.edu

September 16, 2019
"""

import torch
import numpy as np

_j = torch.tensor([0.0, 1.0])

def r2c(real_tensor):
    '''Convert from real to complex'''
    real_tensor = real_tensor.unsqueeze(-1)
    imaginary_tensor = real_tensor.clone()
    imaginary_tensor[:] = 0.0
    return torch.cat((real_tensor, imaginary_tensor), -1)

def real(complex_tensor):
    '''extracting the real part of a tensor'''
    return complex_tensor[...,0]

def imag(complex_tensor):
    '''extracting the imaginary part of a tensor'''
    return complex_tensor[...,1]

def conj(complex_tensor):
    '''Compute complex conjugate'''
    complex_conj_tensor          = complex_tensor.clone()
    complex_conj_tensor[..., 1] *= -1.0
    return complex_conj_tensor

def angle(complex_tensor):
    '''Compute phase of the complex tensor'''
    return torch.atan2(complex_tensor[..., 1], complex_tensor[..., 0])

def exponentiate(complex_tensor, a):
    '''calculates exponentiation for complex variables x**a'''
    output         = complex_tensor.clone()
    amplitude      = ((complex_tensor**2).sum(-1))**(0.5*a)
    phase          = angle(complex_tensor)*a
    output[..., 0] = amplitude*torch.cos(phase)
    output[..., 1] = amplitude*torch.sin(phase)
    return output

def exp(complex_tensor):
    '''calculates exponent exp(tensor)'''
    output         = complex_tensor.clone()
    amplitude      = torch.exp(complex_tensor[..., 0])
    output[..., 0] = amplitude*torch.cos(complex_tensor[..., 1])
    output[..., 1] = amplitude*torch.sin(complex_tensor[..., 1])    
    return output

def multiply_complex(complex_tensor1, complex_tensor2):
    '''Compute element-wise multiplication between complex tensors'''
    complex_tensor_mul_real = complex_tensor1[..., 0]*complex_tensor2[..., 0] -\
                              complex_tensor1[..., 1]*complex_tensor2[..., 1]
    complex_tensor_mul_imag = complex_tensor1[..., 0]*complex_tensor2[..., 1] +\
                              complex_tensor1[..., 1]*complex_tensor2[..., 0]
    return torch.stack((complex_tensor_mul_real, complex_tensor_mul_imag), dim=len(complex_tensor_mul_real.shape))

def division_complex(complex_tensor1, complex_tensor2):
    '''Compute element-wise division between complex tensors'''
    denominator             = (complex_tensor2**2).sum(-1)
    complex_tensor_mul_real = (complex_tensor1[..., 0]*complex_tensor2[..., 0] + complex_tensor1[..., 1]*complex_tensor2[..., 1])/denominator
    complex_tensor_mul_imag = (complex_tensor1[..., 1]*complex_tensor2[..., 0] - complex_tensor1[..., 0]*complex_tensor2[..., 1])/denominator
    return torch.stack((complex_tensor_mul_real, complex_tensor_mul_imag), dim=len(complex_tensor_mul_real.shape))

def abs(complex_tensor):
    '''Compute element-wise absolute value of a complex variable'''
    assert complex_tensor.shape[-1]==2, "Complex tensor should have real and imaginary parts."
    output = ((complex_tensor**2).sum(-1))**0.5
    return output    

def convolve_kernel(tensor_in, kernel, n_dim=1, flag_inplace=True):
    '''
    Compute convolution FFT(tensor_in) and kernel
    Required Args:
        tensor_in: variable 1 in real space
        kernel: variable 2 in reciprocal space

    Optional Args [default]
        n_dim: number of dimensions to compute convolution [1]
        flag_inplace: Whether or not compute convolution inplace, result saved in 'tensor_in' [True]
    '''
    if flag_inplace:
        tensor_in = torch.fft(tensor_in, signal_ndim=n_dim)
        tensor_in = multiply_complex(tensor_in, kernel)
        tensor_in = torch.ifft(tensor_in,signal_ndim=n_dim)
        return tensor_in
    else:
        output = torch.fft(tensor_in, signal_ndim=n_dim)
        output = multiply_complex(output, kernel)
        output = torch.ifft(output,signal_ndim=n_dim)             
        return output

def fftshift(tensor_in, axes=None):
    '''Custom implemented fftshift operator'''
    ret = tensor_in.clone()
    axes= np.atleast_1d(axes)
    for axis in axes:
        ret =  torch.roll(ret, ret.shape[axis]//2, dims=int(axis))
    return ret

def ifftshift(tensor_in, axes=None):
    '''Custom implemented ifftshift operator'''
    ret = tensor_in.clone()
    axes= np.atleast_1d(axes)
    for axis in axes:
        ret =  torch.roll(ret, -1*int(ret.shape[axis]//2), dims=int(axis))
    return ret

class ComplexConj(torch.autograd.Function):
    '''Complex multiplication class for autograd'''
    @staticmethod
    def forward(ctx, tensor_in):
        return conj(tensor_in)

    @staticmethod
    def backward(ctx, grad_output):
        return conj(grad_output)

class ComplexMul(torch.autograd.Function):
    '''Complex multiplication class for autograd'''
    @staticmethod
    def forward(ctx, input1, input2):
        assert input1.shape[-1]==2, "Complex tensor should have real and imaginary parts."
        assert input2.shape[-1]==2, "Complex tensor should have real and imaginary parts."
        output = multiply_complex(input1, input2)

        ctx.save_for_backward(input1, input2)
        return output

    @staticmethod
    def backward(ctx, grad_output):
        input1, input2 = ctx.saved_tensors
        grad_input1    = multiply_complex(conj(input2), grad_output)
        grad_input2    = multiply_complex(conj(input1), grad_output)
        if len(input1.shape)>len(input2.shape):
            grad_input2 = grad_input2.sum(0)
        elif len(input1.shape)<len(input2.shape):
            grad_input1 = grad_input1.sum(0)

        return grad_input1, grad_input2

class ComplexDiv(torch.autograd.Function):
    '''Complex division class for autograd'''
    @staticmethod
    def forward(ctx, input1, input2):
        assert input1.shape[-1]==2, "Complex tensor should have real and imaginary parts."
        assert input2.shape[-1]==2, "Complex tensor should have real and imaginary parts."
        output = division_complex(input1, input2)

        ctx.save_for_backward(input1, input2)
        return output

    @staticmethod
    def backward(ctx, grad_output):
        input1, input2       = ctx.saved_tensors
        denominator          = (input2**2).sum(-1)
        grad_input1          = input2.clone()
        grad_input1[..., 0] /= denominator
        grad_input1[..., 1] /= denominator
        grad_input1          = multiply_complex(grad_input1, grad_output)
        grad_input2          = -1*conj(division_complex(input1, multiply_complex(input2, input2)))
        grad_input2          = multiply_complex(grad_input2, grad_output)

        if len(input1.shape)>len(input2.shape):
            grad_input2 = grad_input2.sum(0)
        elif len(input1.shape)<len(input2.shape):
            grad_input1 = grad_input1.sum(0)

        return grad_input1, grad_input2

class ComplexAbs(torch.autograd.Function):
    '''Absolute value class for autograd'''
    @staticmethod
    def forward(ctx, tensor_in):
        assert tensor_in.shape[-1]==2, "Complex tensor should have real and imaginary parts."
        output         = ((tensor_in**2).sum(-1))**0.5

        ctx.save_for_backward(tensor_in)
        return output

    @staticmethod
    def backward(ctx, grad_output):
        tensor_in,         = ctx.saved_tensors
        grad_input     = torch.stack((grad_output, torch.zeros_like(grad_output)), dim=len(grad_output.shape))
        phase_input    = angle(tensor_in)
        phase_input    = torch.stack((torch.cos(phase_input), torch.sin(phase_input)), dim=len(grad_output.shape))
        grad_input     = multiply_complex(phase_input, grad_input)
        return 0.5*grad_input

class ComplexAbs2(torch.autograd.Function):
    '''Absolute value squared class for autograd'''
    @staticmethod
    def forward(ctx, tensor_in):
        assert tensor_in.shape[-1]==2, "Complex tensor should have real and imaginary parts."
        output         = multiply_complex(conj(tensor_in), tensor_in)

        ctx.save_for_backward(tensor_in)
        return output[..., 0]

    @staticmethod
    def backward(ctx, grad_output):        
        tensor_in,         = ctx.saved_tensors
        grad_output_c  = torch.stack((grad_output, torch.zeros_like(grad_output)), dim=len(grad_output.shape))
        grad_input     = multiply_complex(tensor_in, grad_output_c)

        return grad_input

class ComplexExp(torch.autograd.Function):
    '''Complex exponential class for autograd'''
    @staticmethod
    def forward(ctx, tensor_in):
        assert tensor_in.shape[-1]==2, "Complex tensor should have real and imaginary parts."
        output = exp(tensor_in)

        ctx.save_for_backward(output)
        return output

    @staticmethod
    def backward(ctx, grad_output):
        output,        = ctx.saved_tensors
        grad_input     = multiply_complex(conj(output), grad_output)
        return grad_input

class ComplexConv(torch.autograd.Function):
    '''Complex exponential class for autograd'''
    @staticmethod
    def forward(ctx, tensor_in, kernel_in, n_dim, flag_inplace):
        ctx.save_for_backward(kernel_in)
        ctx.n_dim = n_dim
        ctx.flag_inplace = flag_inplace
        return convolve_kernel(tensor_in, kernel_in, n_dim, flag_inplace)
    @staticmethod
    def backward(ctx, grad_output):        
        kernel_in, = ctx.saved_tensors
        return convolve_kernel(grad_output, conj(kernel_in), ctx.n_dim, ctx.flag_inplace), convolve_kernel(conj(grad_output), kernel_in, ctx.n_dim, ctx.flag_inplace), None, None