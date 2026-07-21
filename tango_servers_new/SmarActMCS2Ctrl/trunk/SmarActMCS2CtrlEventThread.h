#ifndef SmarActMCS2Ctrl_EventThread
#define SmarActMCS2Ctrl_EventThread

#include <SmarActMCS2Ctrl.h>

class SmarActMCS2CtrlEventThread : public omni_thread
{
    public:
        SmarActMCS2CtrlEventThread(SmarActMCS2Ctrl_ns::SmarActMCS2Ctrl& dev, SA_CTL_DeviceHandle_t handle, Tango::DevBoolean ttydebug);
        ~SmarActMCS2CtrlEventThread() {}
    private:
        void* run_undetached(void* ptr);
        SmarActMCS2Ctrl_ns::SmarActMCS2Ctrl& device;
        SA_CTL_DeviceHandle_t hn;
        Tango::DevBoolean _ttydebug;
};

#endif


