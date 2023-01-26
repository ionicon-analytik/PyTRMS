#include "Python.h"
/* numpy extension: 
 * (see also <https://docs.scipy.org/doc/numpy-1.15.0/user/c-info.how-to-extend.html>) */
#include "numpy/npy_math.h"  // defines NPY_NAN
#include "numpy/ndarrayobject.h"
//#define NPY_NO_DEPRECATED_API NPY_1_7_API_VERSION
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <stdbool.h>

//#include <IcAPI.h>
#include "../deps/icapi/include/IcAPI.h"

#define RAW 0
#define CORR 1
#define CONC 2

#define N_CAL_PARS 2

#define NAME 0
#define INDEX 1

#define SET 3
#define ACT 4
#define NIL 5  // seems to be 0 always...
#define UNIT 6
#define TIME 7


static PyObject *
icapi_GetNumberOfTimebins(PyObject* self, PyObject* args)
{
	char* ip;
	if (!PyArg_ParseTuple(args, "s", &ip))
		return NULL;

    uint32_t timebins;
	if (IcAPI_GetNumberOfTimebins(ip, &timebins) != IcReturnType_ok)
	{
		PyErr_SetString(PyExc_IOError, "error in LabVIEW NSV engine!");
		return NULL;
	}
	return PyLong_FromLong(timebins);
}

static PyObject *
icapi_GetMeasureState(PyObject *self, PyObject *args)
{
	char* ip;
	if (!PyArg_ParseTuple(args, "s", &ip))
		return NULL;

	Common_MeasureState state = 999;
	if (IcAPI_GetMeasureState(ip, &state) != IcReturnType_ok)
	{
		PyErr_SetString(PyExc_IOError, "error in LabVIEW NSV engine!");
		return NULL;
	}
	return PyLong_FromLong(state);
}

static PyObject *
icapi_GetServerState(PyObject *self, PyObject *args)
{
	char* ip;   
	if (!PyArg_ParseTuple(args, "s", &ip))
		return NULL;

	Common_ServerState state = 999;
	if (IcAPI_GetServerState(ip, &state) != IcReturnType_ok)
	{
		PyErr_SetString(PyExc_IOError, "error in LabVIEW NSV engine!");
		return NULL;
	}
	return PyLong_FromLong(state);
}

static PyObject *
icapi_GetVersion(PyObject *self, PyObject *args)
{
    double version;
    char version_string[10];
	IcAPI_GetVersion(&version, version_string, 10);

	return PyUnicode_FromString(version_string);

	return PyLong_FromDouble(version);
}

//   static PyObject*
//   icapi_SetServerAction(PyObject* self, PyObject* args)
//   {
//   	char* ip;
//   	Common_ServerActions action;
//   	if (!PyArg_ParseTuple(args, "si", &ip, &action))
//   		return NULL;
//       
//   	if (IcAPI_SetServerAction(ip, action) != IcReturnType_ok)
//   	{
//   		PyErr_SetString(PyExc_IOError, "error in LabVIEW NSV engine!");
//   		return NULL;
//   	}
//       return Py_None;
//   }

static PyObject *
icapi_GetNumberOfPeaks(PyObject *self, PyObject *args)
{
	char* ip;
	if (!PyArg_ParseTuple(args, "s", &ip))
		return NULL;

	uint32_t n_peaks = 0;
	if (IcAPI_GetNumberOfPeaks(ip, 0, &n_peaks) != IcReturnType_ok)
	{
		PyErr_SetString(PyExc_IOError, "error in LabVIEW NSV engine!");
		return NULL;
	}
	return PyLong_FromLong(n_peaks);
}

static PyObject *
icapi_SetTraceMasses(PyObject *self, PyObject *args)
{
	char* ip;
	PyObject* iarr;
	if (!PyArg_ParseTuple(args, "sO", &ip, &iarr))
		return NULL;

	npy_intp size = PyArray_Size(iarr);
	npy_intp dim = PyArray_DIM(iarr, 0);
	if (size != dim)
	{
		PyErr_SetString(PyExc_ValueError, "array must be 1-dimensional!");
		return NULL;
	}
	int type = PyArray_TYPE(iarr);
	if (type != NPY_FLOAT)
	{
		PyErr_SetString(PyExc_ValueError, "expected type np.float32!");
		return NULL;
	}
#ifdef Mod_DEBUG
	printf("received np-array with type (%d), dim (%d), size (%d).\n", (int)type, (int)dim, (int)size);
#endif
	float* masses = (float*) PyArray_DATA(iarr);
	int32_t len = (int32_t)size;
	if (IcAPI_SetTraceMasses(ip, masses, len) != IcReturnType_ok)
	{
		PyErr_SetString(PyExc_IOError, "error in LabVIEW NSV engine!");
		return NULL;
	}
	return Py_None;
}

static PyObject *
icapi_GetTraceMasses(PyObject *self, PyObject *args)
{
	char* ip;
	if (!PyArg_ParseTuple(args, "s", &ip))
		return NULL;

	uint32_t n_peaks = 0;
	if (IcAPI_GetNumberOfPeaks(ip, 0, &n_peaks) != IcReturnType_ok)
	{
		PyErr_SetString(PyExc_IOError, "error in LabVIEW NSV engine!");
		return NULL;
	}
#ifdef Mod_DEBUG
	printf("allocating np-array with len (%d).\n", n_peaks);
#endif
	float* masses = (float*) malloc(n_peaks * sizeof(float));
	if (IcAPI_GetTraceMasses(ip, masses, n_peaks) != IcReturnType_ok)
	{
		PyErr_SetString(PyExc_IOError, "error in LabVIEW NSV engine!");
		free(masses);
		return NULL;
	}
	npy_intp dims[1] = { n_peaks };

	return PyArray_SimpleNewFromData(1, dims, NPY_FLOAT, (void*)masses);
}

static inline PyObject *
convert_IcTimingInfo(const IcTimingInfo* timing)
{
	PyObject* rel_cycle = PyLong_FromLong(timing->Cycle);
	PyObject* abs_cycle = PyLong_FromLong(timing->CycleOverall);
	PyObject* rel_time = PyFloat_FromDouble(timing->relTime);
	PyObject* abs_time = PyFloat_FromDouble(timing->absTime);

	Py_ssize_t n_objects = 4;
	PyObject* rv = PyTuple_New(n_objects);
	PyTuple_SetItem(rv, 0, rel_cycle);
	PyTuple_SetItem(rv, 1, abs_cycle);
	PyTuple_SetItem(rv, 2, rel_time);
	PyTuple_SetItem(rv, 3, abs_time);

	return rv;
}

typedef Cluster5* TimeCycle_t;

static inline PyObject *
convert_IcTimingInfo2(const TimeCycle_t timing)
{
	PyObject* rel_cycle = PyLong_FromLong(timing->Cycle);
	PyObject* abs_cycle = PyLong_FromLong(timing->OverallCycle);
	PyObject* rel_time = PyFloat_FromDouble(timing->RelTime);
	PyObject* abs_time = PyFloat_FromDouble(timing->AbsTime);

	Py_ssize_t n_objects = 4;
	PyObject* rv = PyTuple_New(n_objects);
	PyTuple_SetItem(rv, 0, rel_cycle);
	PyTuple_SetItem(rv, 1, abs_cycle);
	PyTuple_SetItem(rv, 2, rel_time);
	PyTuple_SetItem(rv, 3, abs_time);

	return rv;
}


static const Py_ssize_t n_autos = 9;  // no constexpr in ANSI-C :(
static_assert ( sizeof(Cluster19) == (9 * sizeof(int32_t)) , "Automation cluster has changed" );
typedef Cluster19 Automation_t;

static inline PyObject *
convert_Automation(const Automation_t* automation)
{
	PyObject* rv = PyTuple_New(n_autos);
	int32_t* p = automation;
	for (size_t i = 0; i < n_autos; i++)
	{
		PyTuple_SetItem(rv, i, *(p+i));
	}
	return rv;
}

static inline bool
convert_tc_tuple(PyObject* tc_tuple, IcTimingInfo* out)
{
	int32_t rel_cycle, abs_cycle;
	double rel_time, abs_time;

	if (!PyArg_ParseTuple(tc_tuple, "iidd", &rel_cycle, &abs_cycle, &rel_time, &abs_time))
		return false;

	out->Cycle = rel_cycle;
	out->CycleOverall = abs_cycle;
	out->relTime = rel_time;
	out->absTime = abs_time;

	return true;
}

static PyObject *
icapi_GetNextTimecycle(PyObject *self, PyObject *args)
{
	char* ip;
	int32_t timeout = 1000;
	if (!PyArg_ParseTuple(args, "si", &ip, &timeout))
		return NULL;

	IcTimingInfo timing;
	IcReturnType err;
	if ((err = IcAPI_GetNextTimecycle(ip, timeout, &timing)) != IcReturnType_ok)
	{
		switch (err) {
		case IcReturnType_error:
			PyErr_SetString(PyExc_IOError, "error in LabVIEW NSV engine!");
			break;
		case IcReturnType_timeout:
			PyErr_SetString(PyExc_TimeoutError, "method timed out");
			break;
		}
		return NULL;
	}
	return convert_IcTimingInfo(&timing);
}

static PyObject *
icapi_SetTraceData(PyObject *self, PyObject *args)
{
	char* ip;
	int32_t trace_type = 0;
	PyObject* tc_tup;
	PyObject* iarr;	
	if (!PyArg_ParseTuple(args, "siOO", &ip, &trace_type, &tc_tup, &iarr))
		return NULL;

	if (!((0 <= trace_type) && (trace_type < 3)))
	{
		PyErr_SetString(PyExc_ValueError, "trace_type must be 0 <= x < 3");
		return NULL;
	}
	npy_intp size = PyArray_Size(iarr);
	npy_intp dim = PyArray_DIM(iarr, 0);
	if (size != dim)
	{
		PyErr_SetString(PyExc_ValueError, "array must be 1-dimensional!");
		return NULL;
	}
	int type = PyArray_TYPE(iarr);
	if (type != NPY_FLOAT)
	{
		PyErr_SetString(PyExc_ValueError, "expected type np.float32!");
		return NULL;
	}
#ifdef Mod_DEBUG
	printf("received np-array with type (%d), dim (%d), size (%d).\n", (int)type, (int)dim, (int)size);
#endif
	float* data = (float*) PyArray_DATA(iarr);
	IcTimingInfo timing;
	if (!convert_tc_tuple(tc_tup, &timing))
		return NULL;

	if (IcAPI_SetTraceDataWithTimingInfo(ip, &timing, trace_type, data, (int32_t)dim) != IcReturnType_ok)
	{
		PyErr_SetString(PyExc_IOError, "error in LabVIEW NSV engine!");
		return NULL;
	}
	return Py_None;
}

static PyObject *
icapi_GetTraceData(PyObject *self, PyObject *args)
{
	char* ip;
    int32_t timeout_ms = 1000;
    int32_t trace_type = 0;
	if (!PyArg_ParseTuple(args, "sii", &ip, &timeout_ms, &trace_type))
		return NULL;

	if (!((0 <= trace_type) && (trace_type < 3)))
	{
		PyErr_SetString(PyExc_ValueError, "trace_type must be 0 <= x < 3");
		return NULL;
	}
	int32_t n_peaks = 0;
	if (IcAPI_GetNumberOfPeaks(ip, 0, &n_peaks) != IcReturnType_ok)
	{
		PyErr_SetString(PyExc_IOError, "error in LabVIEW NSV engine!");
		return NULL;
	}
	IcTimingInfo timing;
	float* data = (float*) malloc(3 * sizeof(float) * n_peaks);
	IcReturnType err;
	if ((err = IcAPI_GetTraceDataWithTimingInfo(ip, timeout_ms, &timing, trace_type, data, n_peaks)) != IcReturnType_ok)
	{
	    free(data);
		switch (err) {
		case IcReturnType_error:
			PyErr_SetString(PyExc_IOError, "error in LabVIEW NSV engine!");
			break;
		case IcReturnType_timeout:
			PyErr_SetString(PyExc_TimeoutError, "method timed out");
			break;
		}
		return NULL;
	}
#ifdef Mod_DEBUG
	printf("done reading arrays of length (%d).\n", (int)n_peaks);
#endif
	npy_intp dims[] = { n_peaks };
	PyObject* oarr = PyArray_SimpleNewFromData(1, dims, NPY_FLOAT, (void*)data);
	PyObject* tc_tuple = convert_IcTimingInfo(&timing);

	PyObject* rv = PyTuple_New(2);
	PyTuple_SetItem(rv, 0, tc_tuple);
	PyTuple_SetItem(rv, 1, oarr);

	return rv;
}

static PyObject *
icapi_GetCurrentSpectrum(PyObject *self, PyObject *args)
{
	char* ip;
	if (!PyArg_ParseTuple(args, "s", &ip))
		return NULL;

	/* define shape of output array */
    uint32_t timebins;
	if (IcAPI_GetNumberOfTimebins(ip, &timebins) != IcReturnType_ok)
	{
		PyErr_SetString(PyExc_IOError, "error in LabVIEW NSV engine!");
		return NULL;
	}
	npy_intp dims[1] = { timebins };
	size_t size = sizeof(float) * (size_t)timebins;
	float* raw_spec = (float*) malloc(size);
    IcTimingInfo timing;
	float cal_pars[N_CAL_PARS] = { 0., 0. };
	if (IcAPI_GetCurrentSpec(ip, raw_spec, &timing, cal_pars, timebins, N_CAL_PARS) != IcReturnType_ok)
	{
		PyErr_SetString(PyExc_IOError, "error in LabVIEW NSV engine!");
	    free(raw_spec);
		return NULL;
	}
#ifdef Mod_DEBUG
	printf("done reading arrays of length (%d) of size (%d)\n", (int)timebins, (int)size);
	printf("allocating %d dimension(s) of %d...\n", 1, (int)dims[0]);
#endif
	PyObject* oarr = PyArray_SimpleNewFromData(1, dims, NPY_FLOAT, raw_spec);
	PyObject* tc_tup = convert_IcTimingInfo(&timing);

	PyObject* rv = PyTuple_New(2);
	PyTuple_SetItem(rv, 0, tc_tup);
	PyTuple_SetItem(rv, 1, oarr);

	return rv;
}

static PyObject *
icapi_GetNextSpectrum(PyObject *self, PyObject *args)
{
	char* ip;
	int32_t timeout_ms = 1000;
	if (!PyArg_ParseTuple(args, "si", &ip, &timeout_ms))
		return NULL;

	/* define shape of output array */
	uint32_t timebins;
	if (IcAPI_GetNumberOfTimebins(ip, &timebins) != IcReturnType_ok)
	{
		PyErr_SetString(PyExc_IOError, "error in LabVIEW NSV engine!");
		return NULL;
	}
	npy_intp dims[1] = { timebins };
	size_t size = sizeof(float) * (size_t)timebins;
	float* raw_spec = (float*) malloc(size);
	IcTimingInfo timing;
	float cal_pars[N_CAL_PARS] = { 0., 0. };
	IcReturnType err;
	if ((err = IcAPI_GetNextSpec(ip, timeout_ms, &timing, raw_spec, cal_pars, timebins, N_CAL_PARS)) != IcReturnType_ok)
	{
		free(raw_spec);
		switch (err) {
		case IcReturnType_error:
			PyErr_SetString(PyExc_IOError, "error in LabVIEW NSV engine!");
			break;
		case IcReturnType_timeout:
			PyErr_SetString(PyExc_TimeoutError, "method timed out");
			break;
		}
		return NULL;
	}
#ifdef Mod_DEBUG
	printf("done reading arrays of length (%d) of size (%d)\n", (int)timebins, (int)size);
	printf("allocating %d dimension(s) of %d...\n", 1, (int)dims[0]);
#endif
	PyObject* oarr = PyArray_SimpleNewFromData(1, dims, NPY_FLOAT, raw_spec);
	PyObject* tc_tup = convert_IcTimingInfo(&timing);

	PyObject* rv = PyTuple_New(2);
	PyTuple_SetItem(rv, 0, tc_tup);
	PyTuple_SetItem(rv, 1, oarr);

	return rv;
}

static PyObject *
convert_FloatArray(FloatArray arr)
{
	if ((arr == NULL) || (arr[0] < 100ul))
	{
		PyErr_SetString(PyExc_IOError, "empty FloatArray");
		return NULL;
	}
	FloatArrayBase base = arr[0][0];
	int32_t dims = base.dimSize;
	float* source = base.Numeric;

	PyObject* rv = PyArray_SimpleNew(1, dims, NPY_FLOAT);

	memcpy(PyArray_DATA(rv), source, dims);

	return rv;
}

static PyObject *
icapi_GetFullCycledata(PyObject *self, PyObject *args)
{
	char* ip;
	int32_t timeout_ms = 1000;
	if (!PyArg_ParseTuple(args, "si", &ip, &timeout_ms))
		return NULL;

	uint32_t abs_cycle;
	CommonTypes_TD_ACQ_FullCycleData data;
	IcReturnType err;
	if ((err = IcAPI_GetFullCycleData(ip, timeout_ms, &abs_cycle, &data)) != IcReturnType_ok)
	{
		switch (err) {
		case IcReturnType_error:
			PyErr_SetString(PyExc_IOError, "error in LabVIEW NSV engine!");
			break;
		case IcReturnType_timeout:
			PyErr_SetString(PyExc_TimeoutError, "method timed out");
			break;
		}
		return NULL;
	}
#ifdef Mod_DEBUG
	//printf("done reading arrays of length (%d) of size (%d)\n", (int)timebins, (int)size);
#endif
	PyObject* oarr;
	if ((oarr = convert_FloatArray(data.SpecData._1D)) == NULL)
	{
		return NULL;
	}
	PyObject* tc_tup = convert_IcTimingInfo2(&data.SpecData.TimeCycle);
	PyObject* auto_tup = convert_Automation(&data.Automation);

	PyObject* rv = PyTuple_New(3);
	PyTuple_SetItem(rv, 0, tc_tup);
	PyTuple_SetItem(rv, 1, auto_tup);
	PyTuple_SetItem(rv, 2, oarr);

	return rv;
}

//   static PyObject*
//   icapi_read_PTR_data(PyObject* self, PyObject* args)
//   {
//       if (!IcAPI_CheckConnection()) {
//           PyErr_SetString(PyExc_IOError, "no connection!");
//           return NULL;
//       }
//       LStrHandle sh;
//       int32 dims[2] = { 100, 8 };  /* the passed dims don't seem to matter much */
//   	LStrHandleArray sh_arr = AllocateLStrHandleArray(dims);
//       if (sh_arr == NULL) {
//           char err_msg[100];
//           sprintf(err_msg, "in read_PTR_data :: unable to allocate LStrHandleArray "
//                            "with dims %dx%d!", (int) dims[0], (int) dims[1]);
//   		PyErr_SetString(PyExc_IOError, err_msg);
//   		return NULL;
//       }
//       int32 n_entries, n_fields;  
//   #ifdef Mod_DEBUG
//       puts("reading PTR data...");
//   #endif
//   	IcAPI_readPTRdata(&n_fields, &n_entries, &sh_arr);
//   //    n_entries = (*sh_arr)->dimSizes[0];
//   //    n_fields = (*sh_arr)->dimSizes[1];
//   #ifdef Mod_DEBUG
//       printf("done reading PTR data with n_entries: (%d) / n_fields (%d)\n", n_entries, n_fields);
//       printf("got sh_arr with dims (%dx%d)\n", (*sh_arr)->dimSizes[0], (*sh_arr)->dimSizes[1]);
//   #endif
//   	
//       PyObject* rv = PyList_New(n_entries);  // return object (list)
//       int i, j;
//       int* len = (int*) malloc(sizeof(int)*n_fields);  /* the string-lengths in the fields */
//       uChar** field = (uChar**) malloc(sizeof(uChar*)*n_fields);
//       PyObject* entry;  /* becomes a tuple of values */
//   
//       double set, act;  /* temporary variable for float conversion */
//       PyObject* unit;  /* temporary variable to treat the latin1 encoded unit */
//       const char errors[] = "strict";  /* tell PyUnicode_DecodeLatin1 to raise */
//       				     /* a ValueError on decoding error       */
//       for (i=0; i<n_entries; i++)
//       {
//           for (j=0; j<n_fields; j++)
//           {
//               /* this yields the LStrHandle in the array: */
//               sh = (*sh_arr)->String[i*n_fields+j];
//               field[j] = LHStrBuf(sh);
//               len[j] = LHStrLen(sh);
//   #ifdef Mod_DEBUG
//               if (field[j] == NULL)
//                   printf("encountered empty field (%d)...", j);
//               // print string:
//               for(int k=0; k < len[j]; k++)
//                   putchar(field[j][k]);
//               putchar('\t');
//   #endif
//           }
//           /* handle NaN values in set- and act-values.. */
//           if (strncmp(field[SET], "NaN", 3) == 0)
//               set = NPY_NAN;
//           else
//               set = atof(field[SET]);
//           if (strncmp(field[ACT], "NaN", 3) == 0)
//               act = NPY_NAN;
//           else
//               act = atof(field[ACT]);
//           /* here lay the cause for a nasty error: The PyUnicode_New() raised an exception
//            * like this:
//            * ... unicode error: can't decode byte 0xb0 in position 0 ...
//            *
//            * Byte 0xB0 is the degree-sign and this is not expected in utf-8, where all
//            * special characters are encoded with 2-4 bytes and the degree sign is 0x00B0.
//            * The unit is now decoded into a temporary Python unicode object: */
//           unit = PyUnicode_DecodeLatin1(field[UNIT], len[UNIT], errors);
//           /* (this is a safe operation even if field[UNIT] is NULL, because in that      
//            *  case len[UNIT] == 0 and the return value is either '' or None) */
//           entry = Py_BuildValue("(s#,i,s#,d,d,i,O,s#)",
//                            field[NAME], len[NAME], 
//                            atoi(field[INDEX]),
//                            field[ALT_NAME], len[ALT_NAME], 
//                            set,
//                            act,
//                            atoi(field[NIL]),
//                            unit, 
//                            field[TIME], len[TIME]);
//           PyList_SetItem(rv, i, entry);
//   #ifdef Mod_DEBUG
//           puts("\nDone reading PTR-data.");
//   #endif
//   	}
//       Py_DECREF(unit);  // clear temporary Python object
//   
//       free(field);
//       free(len);
//   
//   	return rv;
//   }

//   static PyObject*
//   icapi_write_PTR_data(PyObject* self, PyObject* args)
//   {
//       PyObject* input;
//   	if (!PyArg_ParseTuple(args, "O", &input))
//   		return NULL;
//   
//       bool right_type = PyTuple_Check(input);
//       if (!right_type) {
//   		PyErr_SetString(PyExc_TypeError, "expected tuple of byte strings!");
//           return NULL;
//       }
//   
//       Py_ssize_t len = PyTuple_Size(input);
//       LStr s;
//       LStrPtr sp;
//       LStrHandle sh;
//       const char* key_value;
//       char* buf;
//       PyObject* item;
//       LStrHandleArray1 sh_arr1 = AllocateLStrHandleArray1(len);
//   #ifdef Mod_DEBUG
//       printf("allocated LStrHandleArray1 of dimSize %d, of size %d...\n", 
//               (*sh_arr1)->dimSize, sizeof(sh_arr1));
//   #endif
//   /*
//       char** my_array = (char**) malloc(len*sizeof(char*));
//       if (my_array == NULL) {
//           puts("FATAL: Could not allocate memory for string array!");
//           return NULL;
//       }
//   
//   */
//       for (int pos=0; pos<len; pos++) {
//           item = PyTuple_GetItem(input, pos);
//           key_value = PyBytes_AsString(item);
//           if (key_value == NULL)  /* this would have risen a TypeError already */
//               return NULL;
//   #ifdef Mod_DEBUG
//           printf("writing %s to pos (%d)...\n", key_value, pos);
//   #endif
//           sh = (*sh_arr1)->String[pos];  /* this yields the LStrHandle in the array */
//   //        buf = LHStrBuf(sh);
//   ////        if (buf == NULL) {
//   ////            puts("FATAL: LStrHandleArray1 string buffer out of range!");
//   ////            return NULL;
//   //        }
//           strcpy(s.str, key_value);
//           s.cnt = strlen(key_value);
//   //        LHStrBuf(sh) =
//       }
//   #ifdef Mod_DEBUG
//       puts("writing to PTR data...");
//   #endif
//       IcAPI_writePTRdata(&sh_arr1);
//       MgErr err = DeAllocateLStrHandleArray1(&sh_arr1);
//       if (err != 0)
//           printf("Got LabView error while de-allocating "
//                  "StrHandleArray (errorcode %d)!", err);
//   
//       return Py_None;
//   }

#define MAX_PATH_LEN 260
static PyObject*
icapi_GetCurrentDataFileName(PyObject* self, PyObject* args)
{
	char* ip;
	if (!PyArg_ParseTuple(args, "s", &ip))
		return NULL;

    int32_t len = MAX_PATH_LEN;
    char raw_file[MAX_PATH_LEN];
    char file[MAX_PATH_LEN];
	if (IcAPI_GetCurrentDataFileName(ip, raw_file, len) != IcReturnType_ok)
	{
		PyErr_SetString(PyExc_IOError, "error in LabVIEW NSV engine!");
		return NULL;
	}
    strncpy(file, raw_file, MAX_PATH_LEN);
    const char errors[] = "strict";  /* raise ValueError on decoding error */
    PyObject* rv = PyUnicode_DecodeLatin1(file, len, errors);

    return rv;
}

/*
// TODO fill in more templates...


template:

static PyObject*
icapi_read_PTR_data(PyObject* self, PyObject* args)
{

}

*/

/* ------------------------------------------------- */
static PyMethodDef Methods[] = {
    {"icapi_GetNumberOfTimebins", icapi_GetNumberOfTimebins, METH_VARARGS, 
        "Returns the number of timebins."},
	{"GetMeasureState", icapi_GetMeasureState, METH_VARARGS,
		"Get current measure state.\n\n"
        "Use the dictionary 'measure_state' in this module \n"
        "to decode the state."},
	{"GetServerState", icapi_GetServerState, METH_VARARGS,
		"Get current server state.\n\n"
        "Use the dictionary 'server_state' in this module \n"
        "to decode the state."},
	{"GetVersion", icapi_GetVersion, METH_VARARGS,
		"Get IcAPI.dll version used."},
//	{"GetServerAction", icapi_GetServerAction, METH_VARARGS,
//		"Get current server action.\n\n"
//        "Use the dictionary 'server_actions' in this module "
//        "to decode the state."},
//	{"SetServerAction", icapi_GetServerAction, METH_VARARGS,
//		"Set the current server action.\n\n"
//        "Expects an enumerated integer value as argument."
//        "Use the dictionary 'server_actions' in this module "
//        "to find the desired enum."},
//	{"GetNumberOfPeaks", icapi_GetNumberOfPeaks, METH_VARARGS,
//		"Returns number of peaks."},
    {"GetNumberOfPeaks", icapi_GetNumberOfPeaks, METH_VARARGS,
        "Returns the number of peaks in the IoniTOF peaktable.\n\n"
		"DEPRECATED :: use GetTraceMasses(ip).size with the same effect!"
	},
	{"SetTraceMasses", icapi_SetTraceMasses, METH_VARARGS,
		"Sets the masses of the current peaktable a numpy array.\n\n"
	},
	{"GetTraceMasses", icapi_GetTraceMasses, METH_VARARGS,
		"Gets the masses of the current peaktable a numpy array.\n\n"
	},
	{"GetNextTimecycle", icapi_GetNextTimecycle, METH_VARARGS,
		"Wait for the next cycle and return rel-cycle and abs-cycle.\n\n"
		"Arguments:\n"
		"\tip\n"
		"\ttimeout_ms: timeout in milliseconds\n"
		"Returns: a timing-tuple, see 'GetCurrentSpectrum()'."
	},
	{"SetTraceData", icapi_SetTraceData, METH_VARARGS,
		"Sets the current data of the given trace as a numpy array.\n\n"
		"The size of the array should correspond to the mass-list,\n"
		"see 'Get-/SetTraceMasses()'.\n\n"
		"Arguments:\n"
		"\tip\n"
		"\ttrace_type: one of 0 (raw), 1 (corr), 2 (conc)\n"
		"\ttc_tup: tuple with (rel-cycle, abs-cycle, rel-time, abs-time\n"
		"\tinput-array: np.array(dtype=np.float32) with trace data\n"
		"\n"
		"Returns: a tuple with (timing, data), see 'GetCurrentSpectrum()'."
	},
	{"GetTraceData", icapi_GetTraceData, METH_VARARGS,
		"Gets the current data of all traces as a numpy array.\n\n"
		"The size of the array should correspond to the mass-list,\n"
		"see 'Get-/SetTraceMasses()'.\n\n"
		"Arguments:\n"
		"\tip\n"
		"\ttimeout_ms: timeout in milliseconds\n"
		"\ttrace_type: one of 0 (raw), 1 (corr), 2 (conc)\n"
		"\n"
		"Returns: a tuple with (timing, data), see 'GetCurrentSpectrum()'."
	},
	{"GetCurrentSpectrum", icapi_GetCurrentSpectrum, METH_VARARGS,
		"Gets the timestamp and current spectrum as numpy array.\n\n"
        "The return value is a tuple (timing, spectrum), where the \n"
        "timestamp is a tuple of 4 values: (rel-cycle, abs-cycle,\n"
		"rel-time, abs-time), where the rel-cycle is relative to \n"
		"the current file and the abs-time is a LabVIEW timestamp:\n"
        "the absolute time in seconds after 1st Jan 1904.\n\n"
		"Arguments:\n"
		"\tip: every method of the icapi module takes an ip as first\n"
		"\t    argument. May be 'localhost' for the current machine.\n"
		"\n"
		"Returns: a tuple with (timing, data)."
	},
	{"GetNextSpectrum", icapi_GetNextSpectrum, METH_VARARGS,
		"Gets the timestamp and next available spectrum as numpy array.\n\n"
		"This takes a 'timeout_ms' as a second parameter, which is\n"
		"the time in milliseconds to wait for a new spectrum to arrive.\n"
		"Raises a TimoutError if no new spectrum is read.\n\n"
		"Arguments:\n"
		"\tip\n"
		"\ttimeout_ms: timeout in milliseconds\n"
		"\n"
		"Returns: a tuple with (timing, data), see 'GetCurrentSpectrum()'."
	},
	{"GetFullCycledata", icapi_GetFullCycledata, METH_VARARGS,
		"Gets the timestamp and next available full-cycle data.\n\n"
		"The full-cycle contains ... TODO :: will ich hier ALLES ausgeben??\n"
		"This takes a 'timeout_ms' as a second parameter, which is\n"
		"the time in milliseconds to wait for a new spectrum to arrive.\n"
		"Raises a TimoutError if no new spectrum is read.\n\n"
		"Arguments:\n"
		"\tip\n"
		"\ttimeout_ms: timeout in milliseconds\n"
		"\n"
		"Returns: a tuple with (timing, data), see 'GetCurrentSpectrum()'."
	},
    {"GetCurrentDataFileName", icapi_GetCurrentDataFileName, METH_VARARGS,
        "Gets the current source file name."},
//	{"read_PTR_data", icapi_read_PTR_data, METH_VARARGS,
//		"Returns the PTR data."},
// 	{"write_PTR_data", icapi_write_PTR_data, METH_VARARGS,
// 		"Write to the PTR set values\n\n."
//         "Expects a tuple of key-value byte strings like (b'key:value',..), \n"
//         "where `key` must be a valid PTR data name as returned \n"
//         "by `read_PTR_data()`. The encoding is expected to be Latin1.\n"},
	{NULL, NULL, 0, NULL}  /* Sentinel */
};

static struct PyModuleDef icapi = {
	PyModuleDef_HEAD_INIT,
	"icapi",   	/* name of the module */
	NULL,     	/* module documentation, may be NULL */
	-1,       	/* size of per-interpreter state of the module,
	             	   or -1 if the module keeps state in global variables */
	Methods
};

/* ------------------------------------------------- */
PyMODINIT_FUNC
PyInit_icapi(void)  /* must be PyInit_name, where name is the name of the module */
{
	import_array();  // import numpy 

	PyObject* mod = PyModule_Create(&icapi);
    if (mod == NULL)
        return NULL;

    // add list of tuples with...
    PyObject *val;
    Py_ssize_t len = 0;

    // Measure State:
    PyObject* MeasureState = PyList_New(len);
    Py_INCREF(MeasureState);  /* the module retains a reference to its dictionary */
    // map unicode strings to enum:
    val = Py_BuildValue("(s,i)", "ReadyIdle", Common_MeasureState_ReadyIdle);
    PyList_Append(MeasureState, val);
    val = Py_BuildValue("(s,i)", "NotReady", Common_MeasureState_NotReady);
    PyList_Append(MeasureState, val);
    val = Py_BuildValue("(s,i)", "CloseServer", Common_MeasureState_CloseServer);
    PyList_Append(MeasureState, val);
    val = Py_BuildValue("(s,i)", "WriteCalibration", Common_MeasureState_WriteCalibration);
    PyList_Append(MeasureState, val);
    val = Py_BuildValue("(s,i)", "ShowTofDaqDialog", Common_MeasureState_ShowTofDaqDialog);
    PyList_Append(MeasureState, val);
    val = Py_BuildValue("(s,i)", "StartTofDaqRec", Common_MeasureState_StartTofDaqRec);
    PyList_Append(MeasureState, val);
    val = Py_BuildValue("(s,i)", "LoadCalibration", Common_MeasureState_LoadCalibration);
    PyList_Append(MeasureState, val);
    val = Py_BuildValue("(s,i)", "WriteNewParametersInProgress", Common_MeasureState_WriteNewParametersInProgress);
    PyList_Append(MeasureState, val);
    val = Py_BuildValue("(s,i)", "TofDaqRecNotRunning", Common_MeasureState_TofDaqRecNotRunning);
    PyList_Append(MeasureState, val);
    val = Py_BuildValue("(s,i)", "MeasurementActive", Common_MeasureState_MeasurementActive);
    PyList_Append(MeasureState, val);

    // Server State:
    PyObject* ServerState = PyList_New(len);
    Py_INCREF(ServerState);  /* the module retains a reference to its dictionary */
    // map unicode strings to enum:
    val = Py_BuildValue("(s,i)", "OK", Common_ServerState_OK);
    PyList_Append(ServerState, val);
    val = Py_BuildValue("(s,i)", "Unknown", Common_ServerState_Unknown);
    PyList_Append(ServerState, val);
    val = Py_BuildValue("(s,i)", "Disconnected", Common_ServerState_Disconnected);
    PyList_Append(ServerState, val);
    val = Py_BuildValue("(s,i)", "NotInitialized", Common_ServerState_NotInitialized);
    PyList_Append(ServerState, val);
    val = Py_BuildValue("(s,i)", "Closed", Common_ServerState_Closed);
    PyList_Append(ServerState, val);
    val = Py_BuildValue("(s,i)", "Busy", Common_ServerState_Busy);
    PyList_Append(ServerState, val);
    val = Py_BuildValue("(s,i)", "StartUp", Common_ServerState_StartUp);
    PyList_Append(ServerState, val);
    val = Py_BuildValue("(s,i)", "Warning", Common_ServerState_Warning);
    PyList_Append(ServerState, val);
    val = Py_BuildValue("(s,i)", "Error", Common_ServerState_Error);
    PyList_Append(ServerState, val);

    // Server Actions:
    PyObject* ServerActions = PyList_New(len);
    Py_INCREF(ServerActions);  /* the module retains a reference to its dictionary */
    // map unicode strings to enum:
    val = Py_BuildValue("(s,i)", "Idle", Common_ServerActions_Idle);
    PyList_Append(ServerActions, val);
    val = Py_BuildValue("(s,i)", "StartMeasQuick", Common_ServerActions_StartMeasQuick);
    PyList_Append(ServerActions, val);
    val = Py_BuildValue("(s,i)", "StopMeasurement", Common_ServerActions_StopMeasurement);
    PyList_Append(ServerActions, val);
    val = Py_BuildValue("(s,i)", "LoadPeaktable", Common_ServerActions_LoadPeaktable);
    PyList_Append(ServerActions, val);
    val = Py_BuildValue("(s,i)", "LoadCalibration", Common_ServerActions_LoadCalibration);
    PyList_Append(ServerActions, val);
    val = Py_BuildValue("(s,i)", "ShowSettings", Common_ServerActions_ShowSettings);
    PyList_Append(ServerActions, val);
    val = Py_BuildValue("(s,i)", "WriteCalibration", Common_ServerActions_WriteCalibration);
    PyList_Append(ServerActions, val);
    val = Py_BuildValue("(s,i)", "ShowFP", Common_ServerActions_ShowFP);
    PyList_Append(ServerActions, val);
    val = Py_BuildValue("(s,i)", "HideFP", Common_ServerActions_HideFP);
    PyList_Append(ServerActions, val);
    val = Py_BuildValue("(s,i)", "Reconnect", Common_ServerActions_Reconnect);
    PyList_Append(ServerActions, val);
    val = Py_BuildValue("(s,i)", "Close_No_Prompt", Common_ServerActions_Close_No_Prompt);
    PyList_Append(ServerActions, val);
    val = Py_BuildValue("(s,i)", "ITOF_TDC_Settings", Common_ServerActions_ITOF_TDC_Settings);
    PyList_Append(ServerActions, val);
    val = Py_BuildValue("(s,i)", "ITOF_DI_DO_Dialog", Common_ServerActions_ITOF_DI_DO_Dialog);
    PyList_Append(ServerActions, val);
    val = Py_BuildValue("(s,i)", "Disconnect", Common_ServerActions_Disconnect);
    PyList_Append(ServerActions, val);
    val = Py_BuildValue("(s,i)", "InitTPS", Common_ServerActions_InitTPS);
    PyList_Append(ServerActions, val);
    val = Py_BuildValue("(s,i)", "ShutDownTPS", Common_ServerActions_ShutDownTPS);
    PyList_Append(ServerActions, val);
    val = Py_BuildValue("(s,i)", "Close_With_Prompt", Common_ServerActions_Close_With_Prompt);
    PyList_Append(ServerActions, val);
    val = Py_BuildValue("(s,i)", "StartMeasRecord", Common_ServerActions_StartMeasRecord);
    PyList_Append(ServerActions, val);
    val = Py_BuildValue("(s,i)", "StartMeasAuto", Common_ServerActions_StartMeasAuto);
    PyList_Append(ServerActions, val);
    val = Py_BuildValue("(s,i)", "EditPeakTable", Common_ServerActions_EditPeakTable);
    PyList_Append(ServerActions, val);
    val = Py_BuildValue("(s,i)", "ShowMeasureView", Common_ServerActions_ShowMeasureView);
    PyList_Append(ServerActions, val);
    val = Py_BuildValue("(s,i)", "HideMeasureView", Common_ServerActions_HideMeasureView);
    PyList_Append(ServerActions, val);
    val = Py_BuildValue("(s,i)", "ConnectPTR", Common_ServerActions_ConnectPTR);
    PyList_Append(ServerActions, val);
    val = Py_BuildValue("(s,i)", "DisconnectPTR", Common_ServerActions_DisconnectPTR);
    PyList_Append(ServerActions, val);
    val = Py_BuildValue("(s,i)", "ConnectDetector", Common_ServerActions_ConnectDetector);
    PyList_Append(ServerActions, val);
    val = Py_BuildValue("(s,i)", "DisconnectDetector", Common_ServerActions_DisconnectDetector);
    PyList_Append(ServerActions, val);
    val = Py_BuildValue("(s,i)", "ChangeMeasureView", Common_ServerActions_ChangeMeasureView);
    PyList_Append(ServerActions, val);
    val = Py_BuildValue("(s,i)", "TOF_CoarseCal", Common_ServerActions_TOF_CoarseCal);
    PyList_Append(ServerActions, val);
    val = Py_BuildValue("(s,i)", "iTOF_Reset_avg_View", Common_ServerActions_iTOF_Reset_avg_View);
    PyList_Append(ServerActions, val);
    val = Py_BuildValue("(s,i)", "Load_iTofSupply_Set_File", Common_ServerActions_Load_iTofSupply_Set_File);
    PyList_Append(ServerActions, val);
    val = Py_BuildValue("(s,i)", "Load_And_Set_iTofsupply_Set_File", Common_ServerActions_Load_And_Set_iTofsupply_Set_File);
    PyList_Append(ServerActions, val);
    val = Py_BuildValue("(s,i)", "StartRepeatedMeasurement", Common_ServerActions_StartRepeatedMeasurement);
    PyList_Append(ServerActions, val);
    val = Py_BuildValue("(s,i)", "StopAfterCurrentRun", Common_ServerActions_StopAfterCurrentRun);
    PyList_Append(ServerActions, val);
    val = Py_BuildValue("(s,i)", "SC_TDC_Restart", Common_ServerActions_SC_TDC_Restart);
    PyList_Append(ServerActions, val);
    val = Py_BuildValue("(s,i)", "SC_TDC_Reboot", Common_ServerActions_SC_TDC_Reboot);
    PyList_Append(ServerActions, val);

    // delete key, value
    Py_DECREF(val);

    PyModule_AddObject(mod, "measure_state", MeasureState);
    PyModule_AddObject(mod, "server_state", ServerState);
    PyModule_AddObject(mod, "server_actions", ServerActions);

    return mod;
}

