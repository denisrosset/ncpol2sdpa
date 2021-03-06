# -*- coding: utf-8 -*-
"""
The module contains helper functions to work with MOSEK.

Created on Tue Nov 18 10:51:14 2014

@author: Peter Wittek
"""
import sys
from .sdpa_utils import convert_row_to_sdpa_index


def streamprinter(text):
    """Helper function for printing MOSEK messages in the Python console.
    """
    sys.stdout.write(text)
    sys.stdout.flush()


def convert_to_mosek_index(block_struct, row_offsets, block_offsets, row):
    """MOSEK requires a specific sparse format to define the lower-triangular
    part of a symmetric matrix. This function does the conversion from the
    sparse upper triangular matrix format of Ncpol2SDPA.
    """
    block_index, i, j = convert_row_to_sdpa_index(block_struct, row_offsets,
                                                  row)

    offset = block_offsets[block_index]
    ci = offset + i
    cj = offset + j
    return cj, ci  # Note that MOSEK expect lower-triangular matrices


def convert_to_mosek_matrix(sdpRelaxation):
    """Converts the entire sparse representation of the Fi constraint matrices
    to sparse MOSEK matrices.
    """
    barci = []
    barcj = []
    barcval = []
    barai = []
    baraj = []
    baraval = []
    for k in range(sdpRelaxation.n_vars):
        barai.append([])
        baraj.append([])
        baraval.append([])
    row_offsets = [0]
    block_offsets = [0]
    cumulative_sum = 0
    cumulative_square_sum = 0
    for block_size in sdpRelaxation.block_struct:
        cumulative_sum += block_size
        cumulative_square_sum += block_size ** 2
        row_offsets.append(cumulative_square_sum)
        block_offsets.append(cumulative_sum)
    for row in range(len(sdpRelaxation.F_struct.rows)):
        if len(sdpRelaxation.F_struct.rows[row]) > 0:
            col_index = 0
            for k in sdpRelaxation.F_struct.rows[row]:
                value = sdpRelaxation.F_struct.data[row][col_index]
                i, j = convert_to_mosek_index(sdpRelaxation.block_struct,
                                              row_offsets, block_offsets, row)
                if k > 0:
                    barai[k - 1].append(i)
                    baraj[k - 1].append(j)
                    baraval[k - 1].append(-value)
                else:
                    barci.append(i)
                    barcj.append(j)
                    barcval.append(value)
                col_index += 1
    return barci, barcj, barcval, barai, baraj, baraval


def convert_to_mosek(sdpRelaxation):
    """Convert an SDP relaxation to a MOSEK task.

    :param sdpRelaxation: The SDP relaxation to convert.
    :type sdpRelaxation: :class:`ncpol2sdpa.SdpRelaxation`.

    :returns: :class:`mosek.Task`.
    """
    import mosek
    barci, barcj, barcval, barai, baraj, baraval = \
        convert_to_mosek_matrix(sdpRelaxation)
    bkc = [mosek.boundkey.fx] * sdpRelaxation.n_vars
    blc = [-v for v in sdpRelaxation.obj_facvar]
    buc = [-v for v in sdpRelaxation.obj_facvar]

    env = mosek.Env()
    task = env.Task(0, 0)
    task.set_Stream(mosek.streamtype.log, streamprinter)
    numvar = 0
    numcon = len(bkc)
    BARVARDIM = [sum(sdpRelaxation.block_struct)]

    task.appendvars(numvar)
    task.appendcons(numcon)
    task.appendbarvars(BARVARDIM)
    for i in range(numcon):
        task.putconbound(i, bkc[i], blc[i], buc[i])

    symc = task.appendsparsesymmat(BARVARDIM[0], barci, barcj, barcval)
    task.putbarcj(0, [symc], [1.0])

    for i in range(len(barai)):
        syma = task.appendsparsesymmat(BARVARDIM[0], barai[i], baraj[i],
                                       baraval[i])
        task.putbaraij(i, 0, [syma], [1.0])

    # Input the objective sense (minimize/maximize)
    task.putobjsense(mosek.objsense.minimize)

    return task
