
from quspin.basis.user import user_basis # Hilbert space user basis
from quspin.basis.user import pre_check_state_sig_32,op_sig_32,map_sig_32 # user basis data types
from numba import carray,cfunc # numba helper functions
from numba import uint32,int32,float64,complex128 # numba data types
import numpy as np

######  function to call when applying operators
@cfunc(op_sig_32,
    locals=dict(b=uint32,occ=int32,sps=uint32), )
def op(op_struct_ptr,op_str,site_ind,N,args):
    # using struct pointer to pass op_struct_ptr back to C++ see numba Records
    op_struct = carray(op_struct_ptr,1)[0]
    err = 0
    sps=args[0]  # sps = 2S+1

    site_ind = N - site_ind - 1 # convention for QuSpin for mapping from bits to sites.
    occ = (op_struct.state//sps**site_ind)%sps # occupation
    b = sps**site_ind
    #
    if op_str==43: # "+" is integer value 43 = ord("+")
        '''S_{+} has the element S_{+}|S,ms=0,...,2S> = sqrt((2S-ms)*(ms+1))'''
        op_struct.state += (b if (occ+1)<sps else 0)
        op_struct.matrix_ele *= np.sqrt((occ+1)*(sps-1-occ))

    elif op_str==45: # "-" is integer value 45 = ord("-")
        '''S_{-} has the element S_{-}|S,ms=0,...,2S> = sqrt((2S-ms)*(ms+1))'''
        op_struct.state -= (b if occ>0 else 0)
        op_struct.matrix_ele *= np.sqrt(occ*(sps-occ))

    elif op_str==122: # "z" is integer value 122 = ord("z")
        '''S_z |S,ms=0,...,2S> = (ms-S) |S,ms=0,...,2S>'''
        op_struct.matrix_ele *= occ-(sps-1)/2

    elif op_str==112: # "p" is integer value 112 = ord("p")
        '''P |S,ms=0> = |S,ms=0>'''
        if occ == 0:
            op_struct.matrix_ele *= 1;
        else:
            op_struct.matrix_ele *= 0;
            
    else:
        op_struct.matrix_ele *= 0.0
        err = -1
    #
    return err



######  function to filter states/project states out of the basis
#
@cfunc(pre_check_state_sig_32,
       locals=dict(occ=uint32,sps=uint32,occ0=uint32,i=uint32,next_occ = uint32), )
def pre_check_state(s,N,args):
    """ imposes that that a bit > 0 must be preceded and followed by 0,
    i.e. a particle on a given site must have empty neighboring sites.
    #
    Works only for lattices of up to N=32 sites (otherwise, change mask)
    #
    """
    sps = args[0]
    occ0 = s % sps  # occupation
    occ = s % sps
    s = s // sps
    #out = 1
    for i in range(N-1):
        next_occ = s%sps

        if occ*next_occ != 0:
            return False
        occ = next_occ
        s= s // sps

    if occ*occ0 != 0:
        '''for periodic boundary condition'''
        #out = 0
        return False
    #out = (out==1)
    return True

# @cfunc(pre_check_state_sig_32,
#     locals=dict(s_shift_left=uint32,s_shift_right=uint32), )
# def pre_check_state(s,N,args):
#     """ imposes that that a bit with 1 must be preceded and followed by 0,
#     i.e. a particle on a given site must have empty neighboring sites.
#     #
#     Works only for lattices of up to N=32 sites (otherwise, change mask)
#     #
#     """
#     mask = (0xffffffff >> (32 - N)) # works for lattices of up to 32 sites
#     # cycle bits left by 1 periodically
#     s_shift_left = (((s << 1) & mask) | ((s >> (N - 1)) & mask))
#     #
#     # cycle bits right by 1 periodically
#     s_shift_right = (((s >> 1) & mask) | ((s << (N - 1)) & mask))
#     #
#     return (((s_shift_right|s_shift_left)&s))==0
#
######  define symmetry maps
#

@cfunc(map_sig_32,
    locals=dict(shift=uint32,out=uint32,sps=uint32,i=int32,j=int32,) )
def translation(x,N,sign_ptr,args):
    """ works for all system sizes N. """
    out = 0
    shift = args[0]
    sps = args[1]
    for i in range(N):
        j = (i+shift+N)%N
        out += ( x%sps ) * sps**j
        x //= sps
    #
    return out
#
@cfunc(map_sig_32,
    locals=dict(out=uint32,sps=uint32,i=int32,j=int32) )
def parity(x,N,sign_ptr,args):
    """ works for all system sizes N. """
    out = 0
    sps = args[0]
    for i in range(N):
        j = (N-1) - i
        out += ( x%sps ) * (sps**j)
        x //= sps
    #
    return out
#


def constrained_basis(sps,N,kblock,pblock):
    
    #
    ######  construct user_basis 
    # define maps dict
    #maps = dict(T_block=(translation,N,0,T_args), P_block=(parity,2,0,P_args),)

    T_args=np.array([1,sps],dtype=np.uint32)
    P_args=np.array([sps],dtype=np.uint32)
    maps = dict()
    if kblock is not None:
        maps["T_block"] = (translation,N,kblock,T_args)
        if kblock == 0 and pblock is not None:
            maps["P_block"] = (parity,2,pblock,P_args)   
    elif pblock is not None:
        maps["P_block"] = (parity,2,pblock,P_args)
    else:
        x=1 #print("kblock and pblock is not set, full Hilbert space is used")   
        
    # define op_dict
    op_args = np.array([sps],dtype=np.uint32)
    #op_dict = dict(op=op,op_args=op_args)
    op_dict = dict(op=op,op_args = op_args)
    # define pre_check_state
    pre_check_state_args = np.array([sps],dtype=np.uint32)
    pre_check_state1=(pre_check_state,pre_check_state_args) # None gives a null pointer to args
    # create user basis
    basis = user_basis(np.uint32,N,op_dict,allowed_ops=set("+-zp"),sps=sps,
                        pre_check_state=pre_check_state1,Ns_block_est=2000000,**maps)
    #print(basis)
    return basis
