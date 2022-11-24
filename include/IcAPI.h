#include "extcode.h"
#ifdef __cplusplus
extern "C" {
#endif
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
typedef struct {
	int32_t dimSizes[2];
	LStrHandle String[1];
} LStrHandleArrayBase;
typedef LStrHandleArrayBase **LStrHandleArray;
typedef struct {
	int32_t dimSize;
	LStrHandle String[1];
} LStrHandleArray1Base;
typedef LStrHandleArray1Base **LStrHandleArray1;

/*!
 * IcAPI_CheckConnection
 */
int16_t __cdecl IcAPI_CheckConnection(void);
/*!
 * IcAPI_SetURLofSharedVariables
 */
void __cdecl IcAPI_SetURLofSharedVariables(char IP[]);
/*!
 * IcAPI_GetCurrentDataFileName
 */
void __cdecl IcAPI_GetCurrentDataFileName(char File[], int32_t len);
/*!
 * IcAPI_GetCurrentMasses
 */
void __cdecl IcAPI_GetCurrentMasses(double Array[], int32_t len);
/*!
 * IcAPI_GetCurrentSpec
 */
void __cdecl IcAPI_GetCurrentSpec(float SpecData[], int32_t len);
/*!
 * IcAPI_GetMeasureState
 */
void __cdecl IcAPI_GetMeasureState(Common_MeasureState *MeasureState);
/*!
 * ICAPI_GetNumberOfPeaks
 */
void __cdecl ICAPI_GetNumberOfPeaks(uint32_t *NumOfPeaks);
/*!
 * IcAPI_GetServerState
 */
void __cdecl IcAPI_GetServerState(Common_ServerState *ENU_ServerState);
/*!
 * IcAPI_GetTraceData
 */
void __cdecl IcAPI_GetTraceData(int32_t *sizeS, float Raw[], float Corr[], 
	float Conc[], int32_t len, int32_t len2, int32_t len3);
/*!
 * IcAPI_GetTraceMasses
 */
void __cdecl IcAPI_GetTraceMasses(float Masses[], uint32_t *Size, 
	int32_t len);
/*!
 * IcAPI_SetAutoDataFileName
 */
void __cdecl IcAPI_SetAutoDataFileName(char FileName[]);
/*!
 * IcAPI_SetServerAction
 */
void __cdecl IcAPI_SetServerAction(Common_ServerActions ENU_ServerActions);
/*!
 * IcAPI_StartAcquisition
 */
void __cdecl IcAPI_StartAcquisition(void);
/*!
 * IcAPI_StopAcquisition
 */
void __cdecl IcAPI_StopAcquisition(void);
/*!
 * IcAPI_readPTRdata
 */
void __cdecl IcAPI_readPTRdata(int32_t *x_lenght, int32_t *y_lenght, 
	LStrHandleArray *STR_out);
/*!
 * IcAPI_GetServerAction
 */
void __cdecl IcAPI_GetServerAction(Common_ServerActions *ENU_ServerActions);
/*!
 * IcAPI_SetFCinlet
 */
void __cdecl IcAPI_SetFCinlet(char FCInlet[]);
/*!
 * IcAPI_SetH2O
 */
void __cdecl IcAPI_SetH2O(char H2O[]);
/*!
 * IcAPI_SetIhc
 */
void __cdecl IcAPI_SetIhc(char Ihc[]);
/*!
 * IcAPI_SetIhcCtrl
 */
void __cdecl IcAPI_SetIhcCtrl(char Ihc_Ctrl[]);
/*!
 * IcAPI_SetOPMode
 */
void __cdecl IcAPI_SetOPMode(char OP_Mode[]);
/*!
 * IcAPI_SetPC
 */
void __cdecl IcAPI_SetPC(char PC[]);
/*!
 * IcAPI_SetPdrift
 */
void __cdecl IcAPI_SetPdrift(char Pdrift[]);
/*!
 * IcAPI_SetPdriftCtrl
 */
void __cdecl IcAPI_SetPdriftCtrl(char Pdrift_Ctrl[]);
/*!
 * IcAPI_SetPrimion
 */
void __cdecl IcAPI_SetPrimion(char PrimionIdx[]);
/*!
 * IcAPI_SetSourceValve
 */
void __cdecl IcAPI_SetSourceValve(char SourceValve[]);
/*!
 * IcAPI_SetTransmission
 */
void __cdecl IcAPI_SetTransmission(char Transmission[]);
/*!
 * IcAPI_SetUdrift
 */
void __cdecl IcAPI_SetUdrift(char Udrift[]);
/*!
 * IcAPI_SetUnc
 */
void __cdecl IcAPI_SetUnc(char Unc[]);
/*!
 * IcAPI_SetUql
 */
void __cdecl IcAPI_SetUql(char Uql[]);
/*!
 * IcAPI_SetUs
 */
void __cdecl IcAPI_SetUs(char Us[]);
/*!
 * IcAPI_SetUso
 */
void __cdecl IcAPI_SetUso(char Uso[]);
/*!
 * IcAPI_writePTRdata
 */
void __cdecl IcAPI_writePTRdata(LStrHandleArray1 *Array);
/*!
 * IcAPI_GetArrayLenght
 */
void __cdecl IcAPI_GetArrayLenght(int32_t *CurrentSpecMassesLenght, 
	int32_t *CurrentSpecLenght, int32_t *TraceDataLenght, 
	int32_t *TraceMassesLenght);

MgErr __cdecl LVDLLStatus(char *errStr, int errStrLen, void *module);

/*
* Memory Allocation/Resize/Deallocation APIs for type 'LStrHandleArray'
*/
LStrHandleArray __cdecl AllocateLStrHandleArray (int32 *dimSizeArr);
MgErr __cdecl ResizeLStrHandleArray (LStrHandleArray *hdlPtr, int32 *dimSizeArr);
MgErr __cdecl DeAllocateLStrHandleArray (LStrHandleArray *hdlPtr);

/*
* Memory Allocation/Resize/Deallocation APIs for type 'LStrHandleArray1'
*/
LStrHandleArray1 __cdecl AllocateLStrHandleArray1 (int32 elmtCount);
MgErr __cdecl ResizeLStrHandleArray1 (LStrHandleArray1 *hdlPtr, int32 elmtCount);
MgErr __cdecl DeAllocateLStrHandleArray1 (LStrHandleArray1 *hdlPtr);

void __cdecl SetExcursionFreeExecutionSetting(Bool32 value);

#ifdef __cplusplus
} // extern "C"
#endif

