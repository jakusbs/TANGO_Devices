#ifndef SmarActMCS2Ctrl_HoldingThread
#define SmarActMCS2Ctrl_HoldingThread

#include <SmarActMCS2Ctrl.h>

class SmarActMCS2CtrlHoldingThread : public omni_thread
{
    public:
        SmarActMCS2CtrlHoldingThread(SmarActMCS2Ctrl_ns::SmarActMCS2Ctrl* dev, SA_CTL_DeviceHandle_t handle, int8_t axis, omni_mutex& mut);
        ~SmarActMCS2CtrlHoldingThread() {}
    private:
        void* run_undetached(void* ptr);
        SmarActMCS2Ctrl_ns::SmarActMCS2Ctrl* device;
        SA_CTL_DeviceHandle_t hn;
        int8_t ax;
        omni_mutex& mutex;
};

#endif


