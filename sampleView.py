from pickle import NONE
import neural_renderer as nr
import os
from skimage.io import imsave
import torch
import math
from derender import utils, rendering
import numpy as np
import sys
import trimesh

def sampleView(objFolder, objIndex):
    print("====Start sample view component "+ objIndex +" ====")

    ## same camera parameter with RADAR
    image_size = 256
    fov = 10
    ori_z = 12.5
    world_ori=[0,0,ori_z] ## make sure the camera pose is the same
    sor_circum = 24

    # initial setting
    device = 'cuda:0'
    current_dir = os.path.dirname(os.path.realpath(__file__))
    input_dir = current_dir + '/3SweepData/' + objFolder
    test_save_dir = current_dir + '/3SweepData/' + objFolder +'/' + objIndex
    test_dataSet_dir = current_dir + '/3SweepData/' + objFolder +'/TestData/' # final test data folder

    renderer = rendering.get_renderer(world_ori=world_ori, image_size=image_size,fov=fov, fill_back=True)

    # load obj
    vertices, faces, textures = nr.load_obj(
        os.path.join(input_dir, objIndex+'.obj'),normalization=False, load_texture=True, texture_size=8)

    # parse the object data
    radcol_height = vertices.shape[0] // sor_circum
    vertices, faces, textures = parse3SweepObjData(radcol_height,sor_circum,vertices,faces,textures)

    vertices, faces = taubin_smooth_trimesh(vertices,faces,device)

    # sample front view with straight axis object
    sor_curve = rendering.get_straight_sor_curve(radcol_height,device)
    canon_sor_vtx = rendering.get_sor_vtx(sor_curve, sor_circum) # BxHxTx3
    images = renderer.render_rgb(canon_sor_vtx.reshape(1,-1,3), faces[None, :, :], textures[None, :, :, :, :, :])

    # save debug data
    # utils.save_obj(test_save_dir,vertices,faces,suffix='obj_parsed',sep_folder=True)
    # utils.save_images(test_save_dir, images.detach().cpu().numpy(), suffix='sample_view', sep_folder=True)

    ## save the final data
    utils.save_images_objs_pair_data(test_dataSet_dir,images.detach().cpu().numpy(),vertices,faces,objIndex)

    print("====Sample view component "+ objIndex +" ====")

def taubin_smooth_trimesh(vertices,faces,device):

    lamb = 0.5
    nu = 0.5
    iters = 5

    if torch.is_tensor(vertices) and torch.is_tensor(faces):
        # tensor type
        original_mesh = trimesh.Trimesh(vertices=vertices.cpu().numpy(),faces=faces.cpu().numpy())
        smooth_mesh = trimesh.smoothing.filter_taubin(original_mesh, lamb=lamb, nu=nu, iterations=iters, laplacian_operator=None)
        return torch.tensor(smooth_mesh.vertices).to(device), torch.tensor(smooth_mesh.faces).to(device)
    else:
        # numpy type
        original_mesh = trimesh.Trimesh(vertices=vertices,faces=faces)
        smooth_mesh = trimesh.smoothing.filter_taubin(original_mesh, lamb=lamb, nu=nu, iterations=iters, laplacian_operator=None)
        return smooth_mesh.vertices, smooth_mesh.faces

def get_vtx_indexing_offset(vertices):

    ## get the most close to the camera vertice of first row vertices
    mostClosedVerticeIndex = torch.argmax(vertices[:24,-1:]).item() 

    ## half of front side vertices
    leftMostVerticeIndex = mostClosedVerticeIndex - 6
    offset = leftMostVerticeIndex * -1

    return offset

def parse3SweepObjData(radcol_height,sor_circum,vertices,faces=None,textures=None):

    TopAndBottomFaceNumber = (sor_circum-2)*2
    verticesNum = vertices.shape[0]
    ## Vertices
    if vertices is not None:
        ## set the 3Sweep indexing method to fit RADAR
        vertices[26:48] = torch.flip(vertices[26:48],[0])
        new_sor_vtx = vertices.clone()
        new_sor_vtx = torch.roll(new_sor_vtx,-24,0)
        new_sor_vtx[0:24] = vertices[0:24]
        new_sor_vtx[-24:] = vertices[24:48]

        # indexing start offset
        initialIndexOffset = get_vtx_indexing_offset(new_sor_vtx)

        ## roll the circum vertices to fit RADAR initial indexing position
        new_sor_vtx = new_sor_vtx.reshape(1,radcol_height,sor_circum,3) # 1xHxWx3
        new_sor_vtx = torch.roll(new_sor_vtx,initialIndexOffset,2)
        new_sor_vtx = new_sor_vtx.reshape(-1,3)

        ## coordinate system, y & z is opposite
        new_sor_vtx[:,1:]*=-1

     ## Face
    if faces is not None:
        lastRowMap = torch.arange(47,25,-1).to(faces.device)
        firstTwoElement = torch.arange(24,26,1).to(faces.device)
        lastRowMap = torch.cat([firstTwoElement,lastRowMap],0)
        offsetLastRowMap = torch.arange((verticesNum),(verticesNum+sor_circum),1).to(faces.device)
        faces = faces[TopAndBottomFaceNumber:]
        for i, (originValue,mapValue) in enumerate(zip(lastRowMap,offsetLastRowMap)):
            faces[faces==originValue] = mapValue.int()
        indexWithoutFirstRow = faces>(sor_circum-1)
        faces[indexWithoutFirstRow] -= sor_circum

        ## parse the initial position
        if initialIndexOffset < 0:
            newFaces = torch.where((faces+initialIndexOffset)>=(faces//sor_circum)*sor_circum,faces+initialIndexOffset,faces+initialIndexOffset+sor_circum)
        elif initialIndexOffset > 0:
            newFaces = torch.where((faces+initialIndexOffset)>=((faces//sor_circum)+1)*sor_circum,faces+initialIndexOffset,faces+initialIndexOffset-sor_circum)
        else:
            newFaces = faces

    ## Texture (delete first 44 value in textures upper+lower circle)
    if textures is not None:
        textures = textures[TopAndBottomFaceNumber:] 

    return new_sor_vtx,newFaces,textures

if __name__ == '__main__':
    objFolder = 'TestData_20220502/mic_2/'
    objNum = 1
    for i in range(objNum):
        indexStr = str(i +1)
        sampleView(objFolder, indexStr)
    print("====Sample View Complete !!! =====")