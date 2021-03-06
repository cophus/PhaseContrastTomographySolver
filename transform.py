"""
Transform functions for Tomography in Numpy, Scipy, Torch, and Skimage
Estimates affine transform between measured image and predicted image
https://github.com/scikit-image/scikit-image

David Ren      david.ren@berkeley.edu

Dec 28, 2020
"""

import numpy as np
import torch
from skimage.registration import optical_flow_tvl1
from skimage import transform
import scipy.optimize as sop

class ImageTransformOpticalFlow():
    """
    Class written to register stack of images for AET.
    Uses correlation based method to determine subpixel shift between predicted and measured images.
    Input parameters:
        - shape: shape of the image
    """ 
    def __init__(self, shape, method="optical_flow"):
        self.shape = shape
        self.x_lin, self.y_lin = np.meshgrid(np.arange(self.shape[1]), np.arange(self.shape[0]))
        self.xy_lin = np.concatenate((self.x_lin[np.newaxis,], self.y_lin[np.newaxis,])).astype('float32')
        

    def _coordinate_warp(self, transform_vec, xy_lin, xy_flow):
        transform_vec = transform_vec.astype('float32')
        rot_mat = [np.cos(transform_vec[0]), \
                   -np.sin(transform_vec[0]), \
                   np.sin(transform_vec[0]), \
                   np.cos(transform_vec[0])]
        xy_predict = np.zeros_like(xy_lin)
        xy_predict[0,] = rot_mat[0] * xy_lin[0,] + rot_mat[1] * xy_lin[1,] + transform_vec[1]
        xy_predict[1,] = rot_mat[2] * xy_lin[0,] + rot_mat[3] * xy_lin[1,] + transform_vec[2]
        resid = xy_predict - xy_flow
        f_val = 0.5 * np.sum(resid.transpose((1,2,0)).flatten() ** 2)
        f_grad = []
        #theta
        f_grad.append(np.sum((rot_mat[1] * xy_lin[0,] * resid[0,]).flatten()) +\
                      np.sum((-rot_mat[0] * xy_lin[1,] * resid[0,]).flatten()) + \
                      np.sum((rot_mat[0] * xy_lin[0,] * resid[1,]).flatten()) + \
                      np.sum((rot_mat[1] * xy_lin[1,] * resid[1,]).flatten()))
        #dx
        f_grad.append(np.sum((resid[0,]).flatten()))
        #dy
        f_grad.append(np.sum((resid[1,]).flatten()))
        f_grad = np.array(f_grad)
        return f_val.astype('float64'), np.array(f_grad).astype('float64')

    def _estimate_single(self, predicted, measured):
        assert predicted.shape == self.shape
        assert measured.shape == self.shape
        flow = optical_flow_tvl1(predicted, measured)
        flow[[1,0],] = flow[[0,1],]
        xy_flow = self.xy_lin - flow
        _Afunc_coord_warp = lambda transform_vec: self._coordinate_warp(transform_vec, self.xy_lin, xy_flow)    

        #estimate transform matrix from optical flow
        results = sop.fmin_l_bfgs_b(_Afunc_coord_warp, np.array([0.0,0,0]))
        transform_final = results[0]
        if results[2]["warnflag"]:
            transform_final *= 0.0
            print("Transform estimation not converged")

        #inverse warp measured image
        transform_mat = np.array([np.cos(transform_final[0]), \
                                  -np.sin(transform_final[0]), \
                                  np.sin(transform_final[0]), \
                                  np.cos(transform_final[0]), \
                                  transform_final[1], \
                                  transform_final[2]])        
        aff_mat = np.array([transform_mat[[0,1,4]], transform_mat[[2,3,5]],[0,0,1]])
        tform = transform.AffineTransform(matrix = aff_mat)
        measured_warp = transform.warp(measured, tform.inverse, cval = 1.0)

        return measured_warp, transform_final

    def estimate(self, predicted_stack, measured_stack):
        assert predicted_stack.shape == measured_stack.shape
        transform_vec_list = np.zeros((3,measured_stack.shape[2]), dtype="float32")

        #Change from torch array to numpy array
        flag_predicted_gpu = predicted_stack.is_cuda
        if flag_predicted_gpu:
            predicted_stack = predicted_stack.cpu()

        flag_measured_gpu = measured_stack.is_cuda
        if flag_measured_gpu:
            measured_stack = measured_stack.cpu()        
        
        predicted_np = np.array(predicted_stack.detach())
        measured_np  = np.array(measured_stack.detach())
        
        #For each image, estimate the affine transform error
        for img_idx in range(measured_np.shape[2]):
            measured_np[...,img_idx], transform_vec = self._estimate_single(predicted_np[...,img_idx], \
                                                                      measured_np[...,img_idx])
            transform_vec_list[...,img_idx] = transform_vec
        
        #Change data back to torch tensor format
        if flag_predicted_gpu:
            predicted_stack = predicted_stack.cuda()

        measured_np = torch.tensor(measured_np)
        if flag_measured_gpu:
            measured_stack  = measured_stack.cuda()        
            measured_np     = measured_np.cuda()

        return measured_np, torch.tensor(transform_vec_list)
