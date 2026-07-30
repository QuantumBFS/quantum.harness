###########################################################################
#                            example 14                                   #
#  In this script we demonstrate how to use the user_basis to construct   #
#  a spin-1/2 Hamiltonian on a restricted Hilbert space where a spin-up   #
#  on a given lattice site must be preceded and succeeded by a spin-down. #
###########################################################################
from quspin.basis.user import user_basis # Hilbert space user basis
from quspin.basis.user import next_state_sig_32,pre_check_state_sig_32,op_sig_32,map_sig_32 # user basis data types
from numba import carray,cfunc # numba helper functions
from numba import uint32,int32,float64,complex128 # numba data types
import numpy as np

######  function to call when applying operators
@cfunc(op_sig_32, locals=dict(s=int32,b=uint32))
def op(op_struct_ptr,op_str,ind,N,args):
    # using struct pointer to pass op_struct_ptr back to C++ see numba Records
    op_struct = carray(op_struct_ptr,1)[0]
    err = 0
    ind = N - ind - 1 # convention for QuSpin for mapping from bits to sites.
    s = (((op_struct.state>>ind)&1)<<1)-1
    b = (1<<ind)
    # x,y,z is pauli matrix, + is (x+iy) and - is (x-iy)
    if op_str==120: # "x" is integer value 120 (check with ord("x"))
        op_struct.state ^= b
    elif op_str==121: # "y" is integer value 120 (check with ord("y"))
        op_struct.state ^= b
        op_struct.matrix_ele *= 1.0j*s
    elif op_str==122: # "z" is integer value 120 (check with ord("z"))
        op_struct.matrix_ele *= s
    elif op_str==43: # "+" is integer value 43 = ord("+")
        op_struct.state ^= b
        op_struct.matrix_ele *= (1-s)
    elif op_str==45: # "-" is integer value 45 = ord("-")
        op_struct.state ^= b
        op_struct.matrix_ele *= (1+s)
    else:
        op_struct.matrix_ele = 0
        err = -1
    #
    return err
#

######  function to filter states/project states out of the basis
#
@cfunc(pre_check_state_sig_32,
    locals=dict(s_shift_left=uint32,s_shift_right=uint32), )
def pre_check_state(s,N,args):
    """ imposes that that a bit with 1 must be preceded and followed by 0,
    i.e. a particle on a given site must have empty neighboring sites.
    #
    Works only for lattices of up to N=32 sites (otherwise, change mask)
    #
    """
    mask = (0xffffffff >> (32 - N)) # works for lattices of up to 32 sites
    # cycle bits left by 1 periodically
    s_shift_left = (((s << 1) & mask) | ((s >> (N - 1)) & mask))
    #
    # cycle bits right by 1 periodically
    s_shift_right = (((s >> 1) & mask) | ((s << (N - 1)) & mask))
    #
    return (((s_shift_right|s_shift_left)&s))==0



######  define symmetry maps
#
@cfunc(map_sig_32,
    locals=dict(shift=uint32,xmax=uint32,x1=uint32,x2=uint32,period=int32,l=int32,) )
def translation(x,N,sign_ptr,args):
    """ works for all system sizes N. """
    shift = args[0] # translate state by shift sites
    period = N # periodicity/cyclicity of translation
    xmax = args[1]
    #
    l = (shift+period)%period
    x1 = (x >> (period - l))
    x2 = ((x << l) & xmax)
    #
    return (x2 | x1)
#T_args=np.array([1,(1<<N)-1],dtype=np.uint32)

#
@cfunc(map_sig_32,
    locals=dict(out=uint32,s=int32,) )
def parity(x,N,sign_ptr,args):
    """ works for all system sizes N. """
    out = 0 
    s = args[0] # N-1
    #
    out ^= (x&1)
    x >>= 1
    while(x):
        out <<= 1
        out ^= (x&1)
        x >>= 1
        s -= 1
    #
    out <<= s
    return out
#P_args=np.array([N-1],dtype=np.uint32)


def constrained_basis(sps,N,kblock,pblock):
    
    pre_check_state_args = None
    #
    ######  construct user_basis 
    # define maps dict
    #maps = dict(T_block=(translation,N,0,T_args), P_block=(parity,2,0,P_args),)

    # for spin 1/2 only
    T_args=np.array([1,(1<<N)-1],dtype=np.uint32) # [shift, xmax]
    P_args=np.array([N-1],dtype=np.uint32)

    maps = dict()
    if kblock is not None:
        maps["T_block"] = (translation,N,kblock,T_args)
        if kblock == 0 and pblock is not None:
            maps["P_block"] = (parity,2,pblock,P_args)   
    elif pblock is not None:
        maps["P_block"] = (parity,2,pblock,P_args)   
        
    # define op_dict
    op_args = np.array([],dtype=np.uint32)
    op_dict = dict(op=op,op_args=op_args)
    # define pre_check_state
    pre_check_state1=(pre_check_state,pre_check_state_args) # None gives a null pointer to args
    # create user basis
    basis = user_basis(np.uint32,N,op_dict,allowed_ops=set("xyz+-"),sps=2,
                        pre_check_state=pre_check_state1,Ns_block_est=300000,**maps)
    #basis = user_basis(np.uint32,N,op_dict,allowed_ops=set("xyz"),sps=2,
    #                    pre_check_state=pre_check_state1,Ns_block_est=300000,**maps)
    
    return basis