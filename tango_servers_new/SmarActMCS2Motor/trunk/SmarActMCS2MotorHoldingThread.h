#ifndef SmarActMCS2Motor_HoldingThread
#define SmarActMCS2Motor_HoldingThread

#include <SmarActMCS2Motor.h>

class SmarActMCS2MotorHoldingThread : public omni_thread
{
    public:
        SmarActMCS2MotorHoldingThread(string& devname);
        ~SmarActMCS2MotorHoldingThread() {}
    private:
        void* run_undetached(void* ptr);
        Tango::DeviceProxy* device;
        string& device_name;
        void waitForOnState();
};

#endif


