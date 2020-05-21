#!/usr/bin/env python
import sys
sys.path.append('../../image-segmentation-keras')
import keras_segmentation
sys.path.append('..')
from lane_detection_segnet_evaluate import evaluate
import os
import glob
from time import strftime

main_path = os.path.join('.')
data_folder = 'output/prepped_data'
model_folder = 'models'
model_name = 'autolabel_L3_S_slalom'+'_'+strftime("%Y-%d-%m-%H%M") 
prefix = '20191010_L3_S_morning_slalom' #empty prefix = train on all

model_path = os.path.join(main_path,model_folder,model_name)
segmentation_path = os.path.join(main_path, 'output/segmentation', model_name)

os.makedirs(model_path, exist_ok = True)
os.makedirs(segmentation_path, exist_ok = True)

model = keras_segmentation.models.segnet.segnet(n_classes=3,  input_height=360, input_width=640)

#Training
model.train(
    train_images =  os.path.join(main_path, data_folder,'train/images/'+prefix),
    train_annotations = os.path.join(main_path, data_folder,'train/annotations/'+prefix),
    validate = True,
    val_images = os.path.join(main_path, data_folder,'val/images/'+prefix),
    val_annotations = os.path.join(main_path, data_folder,'val/annotations/'+prefix),
    checkpoints_path = model_path, 
    steps_per_epoch = None, #determined inside function
    epochs=5,
    logging = True
)

#Quick testing
test_images = glob.glob(os.path.join(data_folder,'val/images/*'))
test_annotations = glob.glob(os.path.join(data_folder,'val/annotations/*'))
evaluate(model=model , inp_images=test_images, annotations=test_annotations , checkpoints_path=None, epoch = None, visualize = True, output_folder = segmentation_path)