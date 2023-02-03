####################################################
#                                                  #
# testing testing testing                          #
#                                                  #
####################################################
import pytest

import os.path

import pytrms


class xTestReader:  ###### not active #######

    def test_one(self):
        assert os.path.exists('examples/data')

    def test_FileWithPROCESSEDSection_canForceOriginal(self):
        m_PROC = pytrms.load('testdata/jens_processed_2022-03-31_08-59-30.h5')
        t_PROC = m_PROC.get_traces(kind='raw', force_original=False)
        t_ORIG = m_PROC.get_traces(kind='raw', force_original=True)

        #assert t_PROC.iloc[0] == t_ORIG.iloc[0]  # raw should be equal

        t_PROC = m_PROC.get_traces(kind='conc', force_original=False)
        t_ORIG = m_PROC.get_traces(kind='conc', force_original=True)

        #assert t_PROC.iloc[0] == t_ORIG.iloc[0]  # concentrations should not

        # compare with original file...
        m_ORIG = pytrms.load('testdata/jens_original_2022-03-31_08-59-30.h5')

        #assert m_ORIG.get_traces() == m_PROC.get_traces(force_original=True)

    def test_FileWithPROCESSEDSection_readsLabels(self):
        SUT = pytrms.load('testdata/jens_processed_2022-03-31_08-59-30.h5')
        t = SUT.get_traces()

        assert t.columns[0] == 'm015_o'
        assert t.columns[1] == '*(CH3)+'
        assert t.columns[2] == '*(O)+'

    def test_FileWithPROCESSEDSection_defaultToProcessedSection(self):
        m_PROC = pytrms.load('testdata/jens_processed_2022-03-31_08-59-30.h5')

        #assert m_PROC.get_traces() != m_PROC.get_traces(force_original=True)

