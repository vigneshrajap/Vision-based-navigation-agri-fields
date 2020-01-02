#!/usr/bin/env python
import os
import glob
from os.path import expanduser
import argparse
import cv2
import numpy as np
from matplotlib import pyplot as plt
from sensor_msgs.msg import Image
from sklearn.cluster import KMeans

import sliding_window_approach
import sliding_window_approach_c
from geometry_msgs.msg import Pose, PoseArray
import scipy.signal as signal
import timeit

class lane_finder_post_predict():
    '''
    A class to find fitted center of the lane points along the crop rows given an input RGB image.
    '''
    def __init__(self):
       #### Hyperparameters ####
       self.image = Image()
       self.final_img = Image()
       self.warp_img = Image()
       self.invwarp_img = Image()
       self.polyfit_img = Image()

       self.class_number = 2 # Extract Interesting Class (2 - Lanes in this case) from predictions
       self.crop_ratio = 0.2 # Ratio to crop the background parts in the image from top

       #src=np.float32([(0.1,0), (0.8,0), (0,1), (1,1)])
       #src=np.float32([(0.1,0.5), (0.8,0.5), (0,1), (1,1)])
       #src=np.float32([(0.2,0.5), (0.8,0.5), (0.2,0.8), (0.8,0.8)])
       #src=np.float32([(0,0.4), (1,0.4), (0,0.8), (1,0.8)])
       #self.src=np.float32([(0,0.3), (1,0.3), (0,1), (1,1)])
       self.src=np.float32([(0.2,0.5), (0.8,0.5), (0.2,1), (0.8,1)])

       self.dst=np.float32([(0,0), (1,0), (0,1), (1,1)])

       self.margin_l = 35
       self.margin_r = 35
       self.nwindows = 10

       self.curves = []
       self.ploty = []
       self.kmeans = KMeans()
       self.base_size = 0.1
       self.clusters = 2
       self.modifiedCenters = []
       #self.M = []
       self.Minv = []

       self.centerLine = []
       self.output_file = None
       self.base = None
       self.end_points = []
       #self.weights = np.empty([3, 1])

    def end_row_detection(self):
       top_roi =  self.warp_img[0:self.warp_img.shape[0]/2,0:self.warp_img.shape[1]]
       rowdata = np.sum(top_roi, axis=1) # Sum the rows of warped image to determine peaks
       num_zeros = (rowdata == 0).sum() # Count the occurence of zero in np array

       if num_zeros>top_roi.shape[0]/8:

           coldata1 =  np.sum(self.warp_img, axis=0) # Sum the peak cols
           end_col_ind = np.argmax(coldata1, axis=0)

           #im2, cnt, heirarchy = cv2.findContours(self.warp_img, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
           edges = cv2.Canny(self.warp_img,100,200)
           end_row_ind = edges[:,end_col_ind].nonzero()[0]
           #indices = np.where(edges != [0])
           #coordinates = np.array([indices[0],indices[1]])
           #print coordinates[0] #, cv2.countNonZero(coordinates[:][1]==end_col_ind)

           self.end_points = [np.argmin(end_row_ind, axis=0), end_col_ind]
           # plt.plot(coldata1)
           # plt.savefig('/home/vignesh/dummy_folder/e_row'+str(os.path.splitext(self.base)[0][7:11])+'.png')
           # plt.close()
           # print num_zeros

    def lane_fit_on_prediction(self, Roi_img, dst_size):

       self.warp_img, M  = sliding_window_approach.perspective_warp(Roi_img, dst_size, self.src, self.dst) # Perspective warp

       ## End Row Check ##
       # self.end_row_detection()
       #print self.end_points

       coldata =  np.sum(self.warp_img, axis=0) # Sum the columns of warped image to determine peaks

       # window = signal.general_gaussian(40, p=0.5, sig=70)
       # filtered = signal.fftconvolve(window, newdata)
       # filtered = (np.average(newdata) / np.average(filtered)) * filtered
       # filtered = np.roll(filtered, -25)
       # plt.plot(filtered) # plotting by columns

       self.modifiedCenters = signal.find_peaks(coldata, height=60000, distance=self.warp_img.shape[1]/3) #, np.arange(1,100), noise_perc=0.1
       # print self.modifiedCenters #width= (0,self.warp_img.shape[1]/3.25),
       # for p_in in range(len(peakidx[0])):
       #  plt.plot(peakidx_r[0][p_in], rowdata[peakidx_r[0][p_in]], marker='o', markersize=10)
       #plt.show()
       #plt.savefig('/home/vignesh/dummy_folder/hist_row'+str(os.path.splitext(self.base)[0][7:11])+'.png')
       #plt.close()

       # InitialPoints Estimation using K-Means clustering
       #self.kmeans, self.modifiedCenters = sliding_window_approach.initialPoints(self.warp_img,self.base_size,self.clusters)

       # Sliding Window Search
       # polyfit_img, curves, lanes, ploty = sliding_window_approach.sliding_window(self.warp_img, peakidx, self.kmeans, self.nwindows)
       self.polyfit_img, self.curves, self.ploty  = sliding_window_approach_c.sliding_window(self.warp_img, self.modifiedCenters, self.kmeans, self.nwindows)

    def visualize_lane_fit(self, dst_size):

       if len(self.modifiedCenters[0]):
           # Mid Lane for robot desired trajectory
           weights = np.array([len(self.modifiedCenters[0]),1], order='F')
           dist_peaks = abs(self.modifiedCenters[0]-self.warp_img.shape[1]/2) # Distance to center of image

           # In IDW, weights are 1 / distance
           weights = 1.0 / dist_peaks

           # Make weights sum to one
           weights /= weights.sum(axis=0)

           # Multiply the weights for each interpolated point by all observed Z-values
           curves_idw = [[]for y in range(len(self.curves))]
           #curves_idw = np.empty[(len(self.curves))]
           for c_in in range(0, len(self.modifiedCenters[0])):
               # print c_in, weights[c_in]         #, len(self.curves[c_in])

              #curves_idw[c_in] = weights[c_in]*self.curves[c_in] #np.dot(weights, self.curves) #weights*
               curves_idw[c_in] =  (weights[c_in]*self.curves[c_in])

           #print  #curves_idw[0]+curves_idw[1]
           curves_m = np.sum(curves_idw, axis=0)
           midLane = np.array([np.transpose(np.vstack([curves_m, self.ploty]))])
           self.centerLine = midLane.astype(int)
           cv2.polylines(self.polyfit_img, [self.centerLine], 0, (255,0,0), thickness=5, lineType=8, shift=0)

       # Visualize the fitted polygonals (One on each lane and on average curve)
       self.polyfit_img = sliding_window_approach_c.visualization_polyfit(self.polyfit_img, self.curves, self.ploty, self.modifiedCenters)

       # Inverse Perspective warp
       self.invwarp_img, self.Minv = sliding_window_approach.inv_perspective_warp(self.polyfit_img, (dst_size[1], dst_size[0]), self.dst, self.src)

       if len(self.modifiedCenters[0]):
           points= np.zeros((len(self.modifiedCenters[0]),2))
           for mc_in in range(len(self.modifiedCenters[0])):
               point_wp = np.array([self.modifiedCenters[0][mc_in], self.warp_img.shape[0]-5, 1])
               peakidx_i = np.matmul(self.Minv, point_wp) # inverse-M*warp_pt
               peakidx_in = np.array([peakidx_i[0]/peakidx_i[2],peakidx_i[1]/peakidx_i[2]]) # divide by Z point
               peakidx_in = peakidx_in.astype(int)
               points[mc_in] = peakidx_in

               cv2.circle(self.invwarp_img, (peakidx_in[0],peakidx_in[1]), 0, (0,0,255), thickness=25, lineType=8, shift=0)

       # print points[0]

       # for i in midLane_i:
       #   point_wp = np.array([i[0],i[1],1])
       #   midLane_io = np.matmul(Minv, point_wp) # inverse-M*warp_pt
       #   midLane_n = np.array([midLane_io[0]/midLane_io[2],midLane_io[1]/midLane_io[2]]) # divide by Z point
       #   midLane_n = midLane_n.astype(int)
       #   midPoints.append(midLane_n)
         #midPoints.poses.append(Pose((midLane_n[0],midLane_n[1],0),(0,0,0,1)))

       # Combine the result with the original image
       self.final_img = cv2.cvtColor(self.image,cv2.COLOR_GRAY2RGB)
       #final_img = input_image.copy()

       rheight, rwidth = self.final_img.shape[:2]
       self.final_img[int(rheight*self.crop_ratio):rheight,0:rwidth] = cv2.addWeighted(self.final_img[int(rheight*self.crop_ratio):int(rheight),0:rwidth],
                                                               0.8, self.invwarp_img, 1.0, 0)

       radius=50
       axes = (radius,radius)
       angle=0;
       startAngle=-180;
       endAngle=0;
       center=(50,50)
       color=255
       thickness = 3

       cv2.ellipse(self.final_img, center, axes, angle, startAngle, endAngle, color)

       # if len(self.end_points):
       #     a = np.array([[self.end_points[1], self.end_points[0]]], dtype='float32')
       #     a = np.array([a])
       #     pointsOut = cv2.perspectiveTransform(a, self.Minv)
       #     # print np.int(pointsOut[0][0][0]), np.int(pointsOut[0][0][1])
       #     cv2.circle(self.final_img, (np.int(pointsOut[0][0][0]), np.int(pointsOut[0][0][1])), 8, (255, 255, 0), 20)
       #     cv2.line(self.final_img, (0, np.int(pointsOut[0][0][1])), (self.final_img.shape[1]-1, np.int(pointsOut[0][0][1])), (0,0,255), 3)
       #     self.final_img = cv2.putText(self.final_img,  "Reached End of Row!!!",
       #                                      (self.final_img.shape[1]/3, np.int(pointsOut[0][0][1])-10), cv2.FONT_HERSHEY_COMPLEX_SMALL, 1.0,(255,255),1, cv2.LINE_AA)
       #     self.end_points = []

    def run_lane_fit(self):
       # Setting the parameters for upscaling and warping-unwarping
       rheight, rwidth = self.image.shape[:2]
       Roi_img = self.image[int(self.crop_ratio*rheight):rheight,0:rwidth]
       dst_size = Roi_img.shape[:2]
       #print self.image.shape[:2], dst_size
       # Sliding Window Approach on Lanes Class from segmentation Array and fit the poly curves
       self.lane_fit_on_prediction(Roi_img, dst_size)

       # Overlay the inverse warped image on input image
       self.visualize_lane_fit(dst_size)

    def visualization(self, display=False):
        if display:
            cv2.imshow('Prediction', self.final_img)
        if not self.output_file is None:
            cv2.imwrite(self.output_file, self.final_img )

    def lane_fit_on_predicted_image(self, lane_fit = False, display=False): #visualize = None

        if lane_fit:
            self.run_lane_fit()
            self.visualization()
        else:
            self.final_img = None

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Example: Run prediction on an image folder. Example usage: python lane_predict.py --model_prefix=models/resnet_3class --epoch=25 --input_folder=Frogn_Dataset/images_prepped_test --output_folder=.")
    parser.add_argument("--input_folder",default = '', help = "(Relative) path to input image file")
    parser.add_argument("--output_folder", default = '', help = "(Relative) path to output image file. If empty, image is not written.")
    parser.add_argument("--display",default = False, help = "Whether to display video on screen (can be slow)")
    args = parser.parse_args()

    print('Output_folder',args.output_folder)
    im_files = glob.glob(os.path.join(args.input_folder,'*.png'))
    print(os.path.join(args.input_folder+'*.png'))

    lfp = lane_finder_post_predict() #Class object

    for pred_im in im_files:
        if args.output_folder:
            lfp.base = os.path.basename(pred_im)
            lfp.output_file = os.path.join(args.output_folder,"frogn_"+os.path.splitext(lfp.base)[0][7:11])+".jpg" #os.path.splitext(base)[0]
            print(lfp.output_file)
        else:
            output_file = None
        lfp.image = cv2.imread(pred_im, 0)

        #blur_img = cv2.blur(seg_img,(10,10))
        #gausblur_img = cv2.GaussianBlur(seg_img, (5,5),0)
        lfp.image = cv2.medianBlur(lfp.image, 15)
        #bilFilter = cv2.bilateralFilter(img,9,75,75)

        lfp.lane_fit_on_predicted_image(lane_fit = True, display=False) #visualize = "segmentation"

        #t = timeit.Timer("d.lane_fit_on_predicted_image()", "from __main__ import lane_finder_post_predict; d = lane_finder_post_predict()")
        #print t.timeit()

    cv2.destroyAllWindows()
