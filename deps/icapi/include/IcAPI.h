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
	int32_t dimSize;
	float Numeric[1];
} FloatArrayBase;
typedef FloatArrayBase **FloatArray;
typedef struct {
	LStrHandle PriIonSetName;
	FloatArray PriIonSetMasses;
	FloatArray PriIonSetMultiplier;
} Cluster;
typedef struct {
	int32_t dimSize;
	Cluster PrimIonSgl[1];
} ClusterArrayBase;
typedef ClusterArrayBase **ClusterArray;
typedef struct {
	uint8_t Last_PiSetIdx;
	uint8_t Current_PiSetIdx;
	ClusterArray PiSets;
} Cluster1;
typedef struct {
	int32_t CurrIdx;
	LStrHandleArray Names;
} Cluster2;
typedef struct {
	LStrHandle Name;
	int16_t Voltage;
	FloatArray Mass;
	FloatArray Trans;
} Cluster3;
typedef struct {
	int32_t dimSize;
	Cluster3 TransElement[1];
} Cluster3ArrayBase;
typedef Cluster3ArrayBase **Cluster3Array;
typedef struct {
	uint8_t Last_Idx;
	uint8_t Current_Idx;
	Cluster3Array Transsets;
} Cluster4;
typedef struct {
	LStrHandle Inst_Mode_and_Paras;
	Cluster1 PISets;
	Cluster2 Presets;
	Cluster4 TransSets;
} CommonTypes_TDef_Calc_ConzInfo;
typedef struct {
	double Cycle;
	double OverallCycle;
	double AbsTime;
	double RelTime;
	double Run;
	double CntsPerExtract;
} Cluster5;
typedef struct {
	int32_t dimSizes[2];
	float Numeric[1];
} FloatArray1Base;
typedef FloatArray1Base **FloatArray1;
typedef struct {
	Cluster5 TimeCycle;
	FloatArray _1D;
	FloatArray SumIntensities;
	FloatArray1 MonitorPeaks;
} Cluster6;
typedef struct {
	int32_t dimSize;
	LVBoolean Boolean[1];
} LVBooleanArrayBase;
typedef LVBooleanArrayBase **LVBooleanArray;
typedef struct {
	LStrHandle GroupName;
	LStrHandleArray Desc;
	LStrHandleArray Units;
	FloatArray Data;
	LVBooleanArray View;
	HWAVES Timestamp;
} Cluster7;
typedef struct {
	int32_t dimSize;
	Cluster7 notification[1];
} Cluster7ArrayBase;
typedef Cluster7ArrayBase **Cluster7Array;
typedef struct {
	Cluster5 TimeCycle;
	FloatArray1 _2d_Raw;
	FloatArray Sum_Raw;
	FloatArray Sum_Corr;
	FloatArray Sum_Conz;
	FloatArray CalcTraces;
	LStrHandleArray CalcTracesNames;
	FloatArray PeakCenters;
	Cluster7Array AddDataQ;
} Cluster8;
typedef struct {
	int32_t dimSize;
	double Numeric[1];
} DoubleArrayBase;
typedef DoubleArrayBase **DoubleArray;
typedef struct {
	DoubleArray Mass;
	DoubleArray Tbin;
} Cluster9;
typedef struct {
	Cluster9 CalList;
	DoubleArray CalPara;
} Cluster10;
typedef uint16_t  Enum;
#define Enum_NotAvailable 0
#define Enum_Good 1
#define Enum_ComError 2
typedef struct {
	float Lat;
	LStrHandle NorthingInd;
	float Lon;
	LStrHandle EastingInd;
	LStrHandle UTC;
	LStrHandle Status;
	LStrHandle Mode;
} Cluster11;
typedef struct {
	LStrHandle UTC;
	LStrHandle Status;
	float Lat;
	LStrHandle NorthingInd;
	float Lon;
	LStrHandle EastingInd;
	float Speedinknots;
	float Course;
	LStrHandle Date;
	float Magneticvariation;
	LStrHandle Mode;
	LStrHandle MagVar;
} Cluster12;
typedef struct {
	float Speed_knots;
	float COG_true;
	LStrHandle COG_true_Unit;
	float COG_magnetic;
	LStrHandle COG_magnetic_Unit;
	LStrHandle SpeedinknotsN;
	float Speed_kmh;
	LStrHandle Speed_kmH_Unit;
	LStrHandle Mode;
} Cluster13;
typedef struct {
	LStrHandle UTC;
	float Lat;
	LStrHandle NorthingInd;
	float Lon;
	LStrHandle EastingInd;
	int32_t Status;
	int32_t SVsUsed;
	float HDOP;
	float Alt_MSL;
	LStrHandle Unit_Alt;
	float GeoidSep;
	LStrHandle UnitGeoidSep;
	float AgeofDGPSCorr;
	LStrHandle DGPSRefStation;
} Cluster14;
typedef struct {
	int32_t dimSize;
	float PDOP[1];
} FloatArray2Base;
typedef FloatArray2Base **FloatArray2;
typedef struct {
	LStrHandle OPMode;
	int32_t NavMode;
	FloatArray2 SVID;
	int32_t SVsUsed;
	float PDOP;
	float HDOP;
	float VDOP;
} Cluster15;
typedef struct {
	float SVID;
	float El;
	float Az;
	float C_NO;
} Cluster16;
typedef struct {
	int32_t dimSize;
	Cluster16 SatInfo[1];
} Cluster16ArrayBase;
typedef Cluster16ArrayBase **Cluster16Array;
typedef struct {
	int32_t SVsTracked;
	Cluster16Array SVInfo;
} Cluster17;
typedef struct {
	Enum State;
	Cluster11 GxGLL;
	Cluster12 GxRMC;
	Cluster13 GxVTG;
	Cluster14 GxGGA;
	Cluster15 GxGSA;
	Cluster17 GPGSV;
	Cluster17 GLGSV;
} Cluster18;
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
} Cluster19;
typedef struct {
	Cluster6 SpecData;
	Cluster8 TraceData;
	Cluster10 MassCal;
	Cluster18 GPSData;
	Cluster19 Automation;
} CommonTypes_TD_ACQ_FullCycleData;
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
 * IcAPI_GetConcInfo
 */
IcReturnType __cdecl IcAPI_GetConcInfo(char IP[], int32_t timeoutMs, 
	CommonTypes_TDef_Calc_ConzInfo *data);
/*!
 * IcAPI_GetConcInfoJson
 */
IcReturnType __cdecl IcAPI_GetConcInfoJson(char IP[], int32_t timeoutMs, 
	char dataAsString[], int32_t len);
/*!
 * IcAPI_GetFullCycleData
 */
IcReturnType __cdecl IcAPI_GetFullCycleData(char IP[], int32_t timeoutMs, 
	uint32_t *OverallCycle, CommonTypes_TD_ACQ_FullCycleData *data);
/*!
 * IcAPI_GetFullCycleDataJson
 */
IcReturnType __cdecl IcAPI_GetFullCycleDataJson(char IP[], int32_t timeoutMs, 
	uint32_t *OverallCycle, char dataAsString[], int32_t len);
/*!
 * IcAPI_SharedLib_IcAPI_GetNextSpec
 */
IcReturnType __cdecl IcAPI_SharedLib_IcAPI_GetNextSpec(char IP[], 
	int32_t timeoutMs, IcAutomation *Automation, IcTimingInfo *TimingInfo, 
	double CalPara[], float Spectrum[], int32_t len, int32_t len2);
/*!
 * IcAPI_SharedLib_IcAPI_SetParametersScheduled
 */
IcReturnType __cdecl IcAPI_SharedLib_IcAPI_SetParametersScheduled(char IP[], 
	LStrHandleArray *pars);

MgErr __cdecl LVDLLStatus(char *errStr, int errStrLen, void *module);

/*
* Memory Allocation/Resize/Deallocation APIs for type 'LStrHandleArray'
*/
LStrHandleArray __cdecl AllocateLStrHandleArray (int32 elmtCount);
MgErr __cdecl ResizeLStrHandleArray (LStrHandleArray *hdlPtr, int32 elmtCount);
MgErr __cdecl DeAllocateLStrHandleArray (LStrHandleArray *hdlPtr);

/*
* Memory Allocation/Resize/Deallocation APIs for type 'ClusterArray'
*/
ClusterArray __cdecl AllocateClusterArray (int32 elmtCount);
MgErr __cdecl ResizeClusterArray (ClusterArray *hdlPtr, int32 elmtCount);
MgErr __cdecl DeAllocateClusterArray (ClusterArray *hdlPtr);

/*
* Memory Allocation/Resize/Deallocation APIs for type 'FloatArray'
*/
FloatArray __cdecl AllocateFloatArray (int32 elmtCount);
MgErr __cdecl ResizeFloatArray (FloatArray *hdlPtr, int32 elmtCount);
MgErr __cdecl DeAllocateFloatArray (FloatArray *hdlPtr);

/*
* Memory Allocation/Resize/Deallocation APIs for type 'Cluster3Array'
*/
Cluster3Array __cdecl AllocateCluster3Array (int32 elmtCount);
MgErr __cdecl ResizeCluster3Array (Cluster3Array *hdlPtr, int32 elmtCount);
MgErr __cdecl DeAllocateCluster3Array (Cluster3Array *hdlPtr);

/*
* Memory Allocation/Resize/Deallocation APIs for type 'FloatArray1'
*/
FloatArray1 __cdecl AllocateFloatArray1 (int32 *dimSizeArr);
MgErr __cdecl ResizeFloatArray1 (FloatArray1 *hdlPtr, int32 *dimSizeArr);
MgErr __cdecl DeAllocateFloatArray1 (FloatArray1 *hdlPtr);

/*
* Memory Allocation/Resize/Deallocation APIs for type 'Cluster7Array'
*/
Cluster7Array __cdecl AllocateCluster7Array (int32 elmtCount);
MgErr __cdecl ResizeCluster7Array (Cluster7Array *hdlPtr, int32 elmtCount);
MgErr __cdecl DeAllocateCluster7Array (Cluster7Array *hdlPtr);

/*
* Memory Allocation/Resize/Deallocation APIs for type 'LVBooleanArray'
*/
LVBooleanArray __cdecl AllocateLVBooleanArray (int32 elmtCount);
MgErr __cdecl ResizeLVBooleanArray (LVBooleanArray *hdlPtr, int32 elmtCount);
MgErr __cdecl DeAllocateLVBooleanArray (LVBooleanArray *hdlPtr);

/*
* Memory Allocation/Resize/Deallocation APIs for type 'DoubleArray'
*/
DoubleArray __cdecl AllocateDoubleArray (int32 elmtCount);
MgErr __cdecl ResizeDoubleArray (DoubleArray *hdlPtr, int32 elmtCount);
MgErr __cdecl DeAllocateDoubleArray (DoubleArray *hdlPtr);

/*
* Memory Allocation/Resize/Deallocation APIs for type 'FloatArray2'
*/
FloatArray2 __cdecl AllocateFloatArray2 (int32 elmtCount);
MgErr __cdecl ResizeFloatArray2 (FloatArray2 *hdlPtr, int32 elmtCount);
MgErr __cdecl DeAllocateFloatArray2 (FloatArray2 *hdlPtr);

/*
* Memory Allocation/Resize/Deallocation APIs for type 'Cluster16Array'
*/
Cluster16Array __cdecl AllocateCluster16Array (int32 elmtCount);
MgErr __cdecl ResizeCluster16Array (Cluster16Array *hdlPtr, int32 elmtCount);
MgErr __cdecl DeAllocateCluster16Array (Cluster16Array *hdlPtr);

void __cdecl SetExecuteVIsInPrivateExecutionSystem(Bool32 value);

#ifdef __cplusplus
} // extern "C"
#endif

