# ======================================================================
# matscipy - Python materials science tools
# https://github.com/libAtoms/matscipy
#
# Copyright (2014) James Kermode, King's College London
#                  Lars Pastewka, Karlsruhe Institute of Technology
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
# ======================================================================

'''
Compute the spatial correlation of a given function. Distances larger than a cut-off are calculated by fourier transformation, while shorter distances are calculated directly.
coords.shape=(n_atoms,3)
cell_vectors=[[x1,y1,z1],[x2,y2,z2],[x3,y3,z3]]

options:
#1)dimensions of correlation [dim=]
    a: along all 3 dimensions -> total distance: None (default)
    b: along only one dimension, ignoring other components: 0..2
#2)mode to assign the atomic values to the FFT grid points [delta=]
    a: assign value to the nearest grid point: simple (default)
    b: assign value to the 8 nearest grid points, distributed proportional to their distance: else
#3)nomalisation by variance of values [norm=]
    a: off: False (default)
    b: on: True
'''

import numpy as np
from math import floor, ceil
from matscipy.neighbours import neighbour_list
from ase import Atoms


def fractional(xyz,cell):
    cell=np.array(cell,dtype=np.float64)
    abc=np.dot(np.linalg.inv(cell),xyz.T).T
    abc[abc<0]+=1
    abc[abc>1]-=1
    return abc

def spatial_correlation_function(atoms, values, cell_vectors, length_cutoff, output_gridsize=None, FFT_cutoff=None, approx_FFT_gridsize=None, dim=None, delta='simple', norm=False):
    if FFT_cutoff==None:
        FFT_cutoff=length_cutoff/5.

    if output_gridsize==None:
        output_gridsize=0.1

    if approx_FFT_gridsize==None:
        approx_FFT_gridsize=3.

    xyz=atoms.get_positions()
    n_atoms=len(xyz)

    n_lattice_points=np.ceil(cell_vectors.diagonal()/approx_FFT_gridsize)
    FFT_gridsize=cell_vectors.diagonal()/n_lattice_points

    abc=fractional(xyz,cell_vectors)

    if delta=='simple':
        #calc lattice values (add to nearest lattice point)
        Q=np.zeros(shape=(n_lattice_points))
        for _abc, _q in zip(abc, values):
            x,y,z = np.round(_abc*(n_lattice_points-1))
            Q[x,y,z] += _q
    else:
        #proportional distribution on 8 neightbor points
        Q=np.zeros(shape=(n_lattice_points))
        a1, a2, a3 = cell_vectors.T
        for _abc, _q in zip(abc, q):
            x,y,z = _abc*(n_lattice_points-1) #was passiert bei ganzen Zahlen?
            aes=np.array([np.floor(x),np.ceil(x)]).reshape(-1, 1, 1, 1)/(n_lattice_points[0]-1)
            bes=np.array([np.floor(y),np.ceil(y)]).reshape( 1,-1, 1, 1)/(n_lattice_points[1]-1)
            ces=np.array([np.floor(z),np.ceil(z)]).reshape( 1, 1,-1, 1)/(n_lattice_points[2]-1)
            octo=(aes*a1.reshape(1,1,1,-1) + bes*a2.reshape(1,1,1,-1) + ces*a3.reshape(1,1,1,-1))-cartesianN(_abc,cell_vectors).reshape(1,1,1,-1)
            octo=1./(np.sqrt((octo**2).sum(axis=3)))
            Q[np.floor(x):np.ceil(x)+1,np.floor(y):np.ceil(y)+1,np.floor(z):np.ceil(z)+1]+=octo/octo.sum()*_q

    #FFT
    Q_schlange=np.fft.fftn(Q)
    C_schlange=Q_schlange*Q_schlange.conjugate()
    C=np.fft.ifftn(C_schlange)*n_lattice_points.prod()/n_atoms/n_atoms
    C = np.fft.ifftshift(C)

    if dim==None:    
        #distance mapping (for floor/ceil convention see *i*fftshift definition)
        a=np.abs(np.reshape(np.arange(-floor(n_lattice_points[0]/2.),ceil(n_lattice_points[0]/2.),1)/n_lattice_points[0],(-1, 1, 1, 1)))
        b=np.abs(np.reshape(np.arange(-floor(n_lattice_points[1]/2.),ceil(n_lattice_points[1]/2.),1)/n_lattice_points[1],( 1,-1, 1, 1)))
        c=np.abs(np.reshape(np.arange(-floor(n_lattice_points[2]/2.),ceil(n_lattice_points[2]/2.),1)/n_lattice_points[2],( 1, 1,-1, 1)))
        a1, a2, a3 = cell_vectors.T
        r = a*a1.reshape(1,1,1,-1) + b*a2.reshape(1,1,1,-1) + c*a3.reshape(1,1,1,-1)
        dist = np.sqrt((r**2).sum(axis=3))
    elif 0<=dim<3:
        #directional SCFs
        # for floor/ceil convention see *i*fftshift definition
        a=np.abs(np.reshape(np.arange(-floor(n_lattice_points[0]/2.),ceil(n_lattice_points[0]/2.),1)/n_lattice_points[0],(-1, 1, 1, 1)))
        b=np.abs(np.reshape(np.arange(-floor(n_lattice_points[1]/2.),ceil(n_lattice_points[1]/2.),1)/n_lattice_points[1],( 1,-1, 1, 1)))
        c=np.abs(np.reshape(np.arange(-floor(n_lattice_points[2]/2.),ceil(n_lattice_points[2]/2.),1)/n_lattice_points[2],( 1, 1,-1, 1)))
        a1, a2, a3 = cell_vectors.T
        r = a*a1.reshape(1,1,1,-1) + b*a2.reshape(1,1,1,-1) + c*a3.reshape(1,1,1,-1)
        dist=np.abs(r[:,:,:,dim]) #use indices to access directions
    else:
        print('invalid correlation direction: '+str(dim))
        sys.exit()

    nbins=length_cutoff/output_gridsize
    SCF=np.histogram(np.reshape(dist,(-1,1)),bins=np.arange(0,length_cutoff+length_cutoff/nbins,length_cutoff/nbins),weights=np.reshape(np.real(C),(-1,1)))[0]/np.histogram(np.reshape(dist,(-1,1)),bins=np.arange(0,length_cutoff+length_cutoff/nbins,length_cutoff/nbins))[0]
    SCF[np.isnan(SCF)]=0
    if norm:
        v_2_mean=(values**2).mean()
        v_mean_2=(values.mean())**2
        SCF=(SCF-v_mean_2)/(v_2_mean-v_mean_2)


    #close range exact calculation
    index1,index2,dist=neighbour_list('ijd', atoms, cutoff=FFT_cutoff)
    SCF_near=np.histogram(np.reshape(dist,(-1,1))/output_gridsize,bins=range(int(FFT_cutoff/output_gridsize+1)),weights=np.reshape(values[index1]*values[index2],(-1,1)))[0]/np.histogram(np.reshape(dist,(-1,1))/output_gridsize,bins=range(int(FFT_cutoff/output_gridsize+1)))[0]
    SCF_near[np.isnan(SCF_near)]=0
    if norm:
        SCF_near=(SCF_near-v_mean_2)/(v_2_mean-v_mean_2)


    #combine SCF parts
    SCF[:int(FFT_cutoff/output_gridsize)]=SCF_near


    return SCF