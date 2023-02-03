#include "extcode.h"
#ifdef __cplusplus
extern "C" {
#endif
typedef uint16_t  IcReturnType;
#define IcReturnType_ok 0
#define IcReturnType_error 1
#define IcReturnType_timeout 2
typedef uint16_t  Common_MeasureState;
#define Common_MeasureState_ReadyIdle 0
#define Common_MeasureState_MeasurementActive 1
#define Common_MeasureState_TofDaqRecNotRunning 2
#define Common_MeasureState_WriteNewParametersInProgress 3
#define Common_MeasureState_LoadCalibration 4
#define Common_MeasureState_StartTofDaqRec 5
#define Common_MeasureState_ShowTofDaqDialog 6
#define Common_MeasureState_WriteCalibration 7
#define Common_MeasureState_CloseServer 8
#define Common_MeasureState_NotReady 9
typedef struct {
	int32_t Cycle;
	int32_t CycleOverall;
	double absTime;
	double relTime;
} IcTimingInfo;
typedef uint16_t  Common_ServerState;
#define Common_ServerState_Unknown 0
#define Common_ServerState_OK 1
#define Common_ServerState_Error 2
#define Common_ServerState_Warning 3
#define Common_ServerState_StartUp 4
#define Common_ServerState_Busy 5
#define Common_ServerState_Closed 6
#define Common_ServerState_NotInitialized 7
#define Common_ServerState_Disconnected 8
typedef uint16_t  Common_ServerActions;
#define Common_ServerActions_Idle 0
#define Common_ServerActions_StartMeasQuick 1
#define Common_ServerActions_StopMeasurement 2
#define Common_ServerActions_LoadPeaktable 3
#define Common_ServerActions_LoadCalibration 4
#define Common_ServerActions_ShowSettings 5
#define Common_ServerActions_WriteCalibration 6
#define Common_ServerActions_ShowFP 7
#define Common_ServerActions_HideFP 8
#define Common_ServerActions_Reconnect 9
#define Common_ServerActions_Close_No_Prompt 10
#define Common_ServerActions_ITOF_TDC_Settings 11
#define Common_ServerActions_ITOF_DI_DO_Dialog 12
#define Common_ServerActions_Disconnect 13
#define Common_ServerActions_InitTPS 14
#define Common_ServerActions_ShutDownTPS 15
#define Common_ServerActions_Close_With_Prompt 16
#define Common_ServerActions_StartMeasRecord 17
#define Common_ServerActions_StartMeasAuto 18
#define Common_ServerActions_EditPeakTable 19
#define Common_ServerActions_ShowMeasureView 20
#define Common_ServerActions_HideMeasureView 21
#define Common_ServerActions_ConnectPTR 22
#define Common_ServerActions_DisconnectPTR 23
#define Common_ServerActions_ConnectDetector 24
#define Common_ServerActions_DisconnectDetector 25
#define Common_ServerActions_ChangeMeasureView 26
#define Common_ServerActions_TOF_CoarseCal 27
#define Common_ServerActions_iTOF_Reset_avg_View 28
#define Common_ServerActions_Load_iTofSupply_Set_File 29
#define Common_ServerActions_Load_And_Set_iTofsupply_Set_File 30
#define Common_ServerActions_StartRepeatedMeasurement 31
#define Common_ServerActions_StopAfterCurrentRun 32
#define Common_ServerActions_SC_TDC_Restart 33
#define Common_ServerActions_SC_TDC_Reboot 34
#define Common_ServerActions_ChangeTransmission 35
#define Common_ServerActions_ChangeDataSaveSet 36
#define Common_ServerActions_ChangeAutoCALset 37
typedef struct {
	int32_t dimSize;
	LStrHandle String[1];
} LStrHandleArrayBase;
typedef LStrHandleArrayBase **LStrHandleArray;
typedef struct {
	int32_t AUTO_StepNumber;
	int32_t AUTO_RunNumber;
	int32_t AUTO_UseMean;
	int32_t AUTO_StartCycleMean;
	int32_t AUTO_StopCycleMean;
	int32_t AME_ActionNumber;
	int32_t AME_UserNumber;
	int32_t AME_StepNumber;
	int32_t AME_RunNumber;
} IcAutomation;
typedef struct {
	int32_t dimSize;
	float Numeric[1];
} FloatArrayBase;
typedef FloatArrayBase **FloatArray;
typedef struct {
	LStrHandleArray Desc;
	FloatArray Data;
	LStrHandleArray Group;
} IcAddData;
typedef struct {
	int32_t dimSize;
	double Numeric[1];
} DoubleArrayBase;
typedef DoubleArrayBase **DoubleArray;
typedef struct {
	FloatArray Spectrum;
	IcAddData AddData;
	IcAutomation Automation;
	DoubleArray CalPara;
	IcTimingInfo TimingInfo;
} IcFullcycle;
typedef struct {
	LStrHandle SettingName;
	FloatArray Masses;
	FloatArray Multiplier;
} IcPrimaryIon;
typedef struct {
	LStrHandle Name;
	float Voltage;
	FloatArray Mass;
	FloatArray Trans;
} IcTransmission;

/*!
 * IcAPI_GetMeasureState
 */
IcReturnType __cdecl IcAPI_GetMeasureState(char IP[], 
	Common_MeasureState *MeasureState);
/*!
 * IcAPI_GetCurrentSpec
 */
IcReturnType __cdecl IcAPI_GetCurrentSpec(char IP[], float SpecData[], 
	IcTimingInfo *TimingInfo, float CalPara[], int32_t len_specdata, 
	int32_t len_calpara);
/*!
 * IcAPI_ConvertTimingInfo
 */
IcReturnType __cdecl IcAPI_ConvertTimingInfo(float SGL_TimingInfo[], 
	IcTimingInfo *TimingInfo, int32_t len);
/*!
 * IcAPI_GetCurrentDataFileName
 */
IcReturnType __cdecl IcAPI_GetCurrentDataFileName(char IP[], char File[], 
	int32_t len);
/*!
 * Retrieve the length of the mass-table for 'GetTraceMasses(..)'.
 * 
 * The length is written to 'NumOfPeaks' if not NULL.
 * 'timeoutMs' is deprecated (no-op)
 */
IcReturnType __cdecl IcAPI_GetNumberOfPeaks(char IP[], int32_t timeoutMs, 
	uint32_t *NumOfPeaks);
/*!
 * IcAPI_GetNumberOfTimebins
 */
IcReturnType __cdecl IcAPI_GetNumberOfTimebins(char IP[], 
	int32_t *NumOfTimebins);
/*!
 * Get the IcAPI version. 
 */
void __cdecl IcAPI_GetVersion(double *version, char versionString[], 
	int32_t len);
/*!
 * IcAPI_GetServerState
 */
IcReturnType __cdecl IcAPI_GetServerState(char IP[], 
	Common_ServerState *ENU_ServerState);
/*!
 * IcAPI_GetTraceData
 */
IcReturnType __cdecl IcAPI_GetTraceData(char IP[], int32_t timeout_ms, 
	float Raw[], float Corr[], float Conc[], int32_t len, int32_t len2, 
	int32_t len3);
/*!
 * Retrieve the list of exact masses as set in the current peaktable.
 * 
 * The 'Masses' must point to an array of length 'len'.
 * If 'actual_size' is not NULL, the potential array size is written there.
 */
IcReturnType __cdecl IcAPI_GetTraceMasses(char IP[], float Masses[], 
	int32_t len);
/*!
 * IcAPI_SetAutoDataFileName
 */
IcReturnType __cdecl IcAPI_SetAutoDataFileName(char IP[], char FileName[]);
/*!
 * IcAPI_SetServerAction
 */
IcReturnType __cdecl IcAPI_SetServerAction(char IP[], 
	Common_ServerActions ServerActions);
/*!
 * IcAPI_SetParameter
 */
IcReturnType __cdecl IcAPI_SetParameter(char IP[], char par[]);
/*!
 * IcAPI_SetParameters
 */
IcReturnType __cdecl IcAPI_SetParameters(char IP[], LStrHandleArray *pars);
/*!
 * IcAPI_GetAddDataNames
 */
IcReturnType __cdecl IcAPI_GetAddDataNames(char IP[], LStrHandleArray *Names);
/*!
 * IcAPI_GetAddDataValues
 */
IcReturnType __cdecl IcAPI_GetAddDataValues(char IP[], float Values[], 
	double *time, int32_t len);
/*!
 * IcAPI_GetErrorCodes
 */
IcReturnType __cdecl IcAPI_GetErrorCodes(char IP[], int32_t codes[], 
	int32_t len);
/*!
 * IcAPI_GetErrorInfos
 */
IcReturnType __cdecl IcAPI_GetErrorInfos(char IP[], LStrHandleArray *Names);
/*!
 * IcAPI_GetNumberOfAddData
 */
IcReturnType __cdecl IcAPI_GetNumberOfAddData(char IP[], int32_t timeoutMs, 
	uint32_t *NumOfData);
/*!
 * IcAPI_GetAddDataNameByIndex
 */
IcReturnType __cdecl IcAPI_GetAddDataNameByIndex(char IP[], int32_t index, 
	char Name[], int32_t len);
/*!
 * Retrieve the next trace-data with a timeout.
 * 
 * 'timeout_ms' is the time to wait for new data. If no new data has arrived, 
 * return the last data and set the return value to 2 (timeout). 
 * 'TraceType' is one of 0 (raw), 1 (corrected), 2 (concentration).
 * 'data' is the float32 data of length passed with 'len'.
 */
IcReturnType __cdecl IcAPI_GetTraceDataWithTimingInfo(char IP[], 
	int32_t timeout_ms, IcTimingInfo *TimingInfo, int32_t TraceType, 
	float data[], int32_t len);
/*!
 * IcAPI_GetParamter
 */
IcReturnType __cdecl IcAPI_GetParamter(char IP[], char Name[], float *Value);
/*!
 * IcAPI_GetAddDataNamesAsJson
 */
IcReturnType __cdecl IcAPI_GetAddDataNamesAsJson(char IP[], char Names[], 
	int32_t len);
/*!
 * IcAPI_GetParameters
 */
IcReturnType __cdecl IcAPI_GetParameters(char IP[], LStrHandleArray *Names, 
	float Values[], int32_t Indices[], int32_t len, int32_t len2);
/*!
 * IcAPI_GetParametersAsJson
 */
IcReturnType __cdecl IcAPI_GetParametersAsJson(char IP[], char NamesAsJson[], 
	float Values[], int32_t Indices[], int32_t len, int32_t len2);
/*!
 * IcAPI_SetParametersAsJson
 */
IcReturnType __cdecl IcAPI_SetParametersAsJson(char IP[], char pars[]);
/*!
 * Retrieve the length of the mass-table for 'GetTraceMasses(..)'.
 * 
 * The length is written to 'NumOfPeaks' if not NULL.
 * 'timeoutMs' is deprecated (no-op)
 */
IcReturnType __cdecl IcAPI_GetNumberOfPeaksOld(char IP[], int32_t timeoutMs, 
	uint32_t *NumOfPeaks);
/*!
 * IcAPI_GetTraceMassesOld
 */
IcReturnType __cdecl IcAPI_GetTraceMassesOld(char IP[], float Masses[], 
	int32_t len);
/*!
 * IcAPI_GetCurrentSpecOld
 */
IcReturnType __cdecl IcAPI_GetCurrentSpecOld(char IP[], float SpecData[], 
	IcTimingInfo *TimingInfo, float CalPara[], int32_t lenData, 
	int32_t lenCalPara);
/*!
 * Set the current trace-data with the timing info.
 * 
 * 'TimingInfo' converts and saves the timestamp alongside the trace-data
 * 'TraceType' is one of 0 (raw), 1 (corr), 2 (conz)
 * 'data' input vector of length given in 'len'
 */
IcReturnType __cdecl IcAPI_SetTraceDataWithTimingInfo(char IP[], 
	IcTimingInfo *TimingInfo, int32_t TraceType, float data[], int32_t len);
/*!
 * IcAPI_SetTraceMasses
 */
IcReturnType __cdecl IcAPI_SetTraceMasses(char IP[], float Masses[], 
	int32_t len);
/*!
 * IcAPI_SetTraceMassesOld
 */
IcReturnType __cdecl IcAPI_SetTraceMassesOld(char IP[], float Masses[], 
	int32_t len);
/*!
 * Set all current trace-data with the timing info.
 * 
 * 'TimingInfo' converts and saves the timestamp alongside the trace-data
 * 'raw/corr/conz' are input vectors of length given in 'len_xxx'
 */
IcReturnType __cdecl IcAPI_SetTraceData(char IP[], IcTimingInfo *TimingInfo, 
	float raw[], float corr[], float conz[], int32_t len_raw, int32_t len_corr, 
	int32_t len_conz);
/*!
 * Get the TimingInfo for the next cycle within the specified timeout in 
 * milliseconds.
 * 
 * If no new cycle arrived within 'timeout', returns 'IcReturnValue_timeout'.
 * 
 * (Note: The rel-time and abs-time are not filled.)
 */
IcReturnType __cdecl IcAPI_GetNextTimecycle(char IP[], int32_t timeoutMs, 
	IcTimingInfo *TimingInfo);
/*!
 * IcAPI_ADD_CheckAddDataDll
 */
IcReturnType __cdecl IcAPI_ADD_CheckAddDataDll(void);
/*!
 * IcAPI_ADD_Create
 */
IcReturnType __cdecl IcAPI_ADD_Create(char Servername[]);
/*!
 * IcAPI_ADD_Dispose
 */
IcReturnType __cdecl IcAPI_ADD_Dispose(char Servername[]);
/*!
 * IcAPI_ADD_SetData
 */
IcReturnType __cdecl IcAPI_ADD_SetData(char Servername[], float Data[], 
	int32_t len);
/*!
 * IcAPI_ADD_SetDescription
 */
IcReturnType __cdecl IcAPI_ADD_SetDescription(char Servername[], 
	LStrHandleArray *Desc);
/*!
 * IcAPI_ADD_SetDescriptionAsByte
 */
IcReturnType __cdecl IcAPI_ADD_SetDescriptionAsByte(char Servername[], 
	uint8_t Desc[], int32_t len);
/*!
 * IcAPI_ADD_SetUnit
 */
IcReturnType __cdecl IcAPI_ADD_SetUnit(char Servername[], 
	LStrHandleArray *Units);
/*!
 * IcAPI_ADD_SetUnitAsByte
 */
IcReturnType __cdecl IcAPI_ADD_SetUnitAsByte(char Servername[], 
	uint8_t Units[], int32_t len);
/*!
 * IcAPI_GetConcInfoJson
 */
IcReturnType __cdecl IcAPI_GetConcInfoJson(char IP[], int32_t timeoutMs, 
	char dataAsString[], int32_t len);
/*!
 * IcAPI_GetFullCycleDataJson
 */
IcReturnType __cdecl IcAPI_GetFullCycleDataJson(char IP[], int32_t timeoutMs, 
	uint32_t *OverallCycle, char dataAsString[], int32_t len);
/*!
 * IcAPI_GetNextSpec
 */
IcReturnType __cdecl IcAPI_GetNextSpec(char IP[], int32_t timeoutMs, 
	IcAutomation *Automation, IcTimingInfo *TimingInfo, double CalPara[], 
	float Spectrum[], int32_t len, int32_t len2);
/*!
 * IcAPI_GetNextFullCycle
 */
IcReturnType __cdecl IcAPI_GetNextFullCycle(char IP[], int32_t timeoutMs, 
	IcFullcycle *IcFullcycle);
/*!
 * IcAPI_GetCurrentPrimaryIon
 */
IcReturnType __cdecl IcAPI_GetCurrentPrimaryIon(char IP[], 
	IcPrimaryIon *pion);
/*!
 * IcAPI_GetCurrentTransmission
 */
IcReturnType __cdecl IcAPI_GetCurrentTransmission(char IP[], 
	IcTransmission *Transm);
/*!
 * IcAPI_SetParametersScheduled
 */
IcReturnType __cdecl IcAPI_SetParametersScheduled(char IP[], 
	LStrHandleArray *pars);

MgErr __cdecl LVDLLStatus(char *errStr, int errStrLen, void *module);

/*
* Memory Allocation/Resize/Deallocation APIs for type 'LStrHandleArray'
*/
LStrHandleArray __cdecl AllocateLStrHandleArray (int32 elmtCount);
MgErr __cdecl ResizeLStrHandleArray (LStrHandleArray *hdlPtr, int32 elmtCount);
MgErr __cdecl DeAllocateLStrHandleArray (LStrHandleArray *hdlPtr);

/*
* Memory Allocation/Resize/Deallocation APIs for type 'FloatArray'
*/
FloatArray __cdecl AllocateFloatArray (int32 elmtCount);
MgErr __cdecl ResizeFloatArray (FloatArray *hdlPtr, int32 elmtCount);
MgErr __cdecl DeAllocateFloatArray (FloatArray *hdlPtr);

/*
* Memory Allocation/Resize/Deallocation APIs for type 'DoubleArray'
*/
DoubleArray __cdecl AllocateDoubleArray (int32 elmtCount);
MgErr __cdecl ResizeDoubleArray (DoubleArray *hdlPtr, int32 elmtCount);
MgErr __cdecl DeAllocateDoubleArray (DoubleArray *hdlPtr);

void __cdecl SetExecuteVIsInPrivateExecutionSystem(Bool32 value);

#ifdef __cplusplus
} // extern "C"
#endif

