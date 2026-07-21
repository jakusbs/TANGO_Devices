#ifndef SmarActMCS2Ctrl_TrajectoryThread
#define SmarActMCS2Ctrl_TrajectoryThread

#include <SmarActMCS2Ctrl.h>

using namespace SmarActMCS2Ctrl_ns;


class SmarActMCS2CtrlTrajectoryThread : public omni_thread
{
    public:
        SmarActMCS2CtrlTrajectoryThread(SmarActMCS2Ctrl_ns::SmarActMCS2Ctrl& dev, SA_CTL_DeviceHandle_t handle, deque <StreamTargetPtrVector>& trajectoryTargetQueue,
			Tango::DevLong& triggerMode, bool& stop, bool& terminate, omni_condition* startCondition);
        ~SmarActMCS2CtrlTrajectoryThread() {}
		void abortStreaming();
		//void streamHandle(SA_CTL_StreamHandle_t h) {_streamHandle = h;}
    private:
        void* run_undetached(void* ptr);
        SmarActMCS2Ctrl_ns::SmarActMCS2Ctrl& _device;
        SA_CTL_DeviceHandle_t _handle;
		deque <StreamTargetPtrVector>& _trajectoryTargetQueue;
		Tango::DevLong& _triggerMode;
		bool& _stop;
		bool& _terminate;
		omni_condition* _startCondition;
		omni_mutex _abort_mutex;
		bool _trajectoryAbort;
		SA_CTL_StreamHandle_t _streamHandle;
		bool waitForStart(StreamTargetPtrVector& firstLine);
		//SA_CTL_StreamHandle_t _streamHandle;
};

#endif

