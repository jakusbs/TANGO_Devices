#include <SmarActMCS2CtrlHoldingThread.h>
using namespace std;

SmarActMCS2CtrlHoldingThread::SmarActMCS2CtrlHoldingThread(SmarActMCS2Ctrl_ns::SmarActMCS2Ctrl* dev, SA_CTL_DeviceHandle_t handle, int8_t axis, omni_mutex& mut)
    : device(dev), hn(handle), ax(axis), mutex(mut)
{
    
    start_undetached();
}

void* SmarActMCS2CtrlHoldingThread::run_undetached(void* ptr)
{
    //cerr << "Holding thread started\n";
    int32_t value;
    SA_CTL_Result_t retval; 

    device->setProperty(ax, SA_CTL_PKEY_MOVE_MODE, SA_CTL_MOVE_MODE_SCAN_ABSOLUTE);
    if((retval = SA_CTL_Move(hn, ax, 0, 0)) != SA_CTL_ERROR_NONE)
    {
        stringstream tmp;
        tmp << "Failed to move " << (int) ax << " in MOVE_MODE_SCAN_ABSOLUTE: ";
        const char* msg = SA_CTL_GetResultInfo(retval);
        tmp << msg;
        device->set_state(Tango::FAULT);
        device->set_status(tmp.str());
        return (void*) 0;
    }
    for(;;)
    {
        device->getProperty(ax, SA_CTL_PKEY_CHANNEL_STATE, &value);
        if((value & SA_CTL_CH_STATE_BIT_ACTIVELY_MOVING) == 0)
        {
            break;
        }
        usleep(1000);
    }
    if((retval = SA_CTL_Move(hn, ax, 35000, 0)) != SA_CTL_ERROR_NONE)
    {
        if((retval = SA_CTL_Move(hn, ax, 0, 0)) != SA_CTL_ERROR_NONE)
    {
        stringstream tmp;
        tmp << "Failed to move " << (int) ax << " in MOVE_MODE_SCAN_ABSOLUTE: ";
        const char* msg = SA_CTL_GetResultInfo(retval);
        tmp << msg;
        device->set_state(Tango::FAULT);
        device->set_status(tmp.str());
        return (void*) 0;
    }
    }
    for(;;)
    {
        device->getProperty(ax, SA_CTL_PKEY_CHANNEL_STATE, &value);
        if((value & SA_CTL_CH_STATE_BIT_ACTIVELY_MOVING) == 0)
        {
            break;
        }
        usleep(1000);
    }
    device->setProperty(ax, SA_CTL_PKEY_MOVE_MODE, SA_CTL_MOVE_MODE_CL_RELATIVE);
    if((retval = SA_CTL_Move(hn, ax, 0, 0)) != SA_CTL_ERROR_NONE)
    {
        stringstream tmp;
        tmp << "Failed to move " << (int) ax << " in SA_CTL_MOVE_MODE_CL_RELATIVE: ";
        const char* msg = SA_CTL_GetResultInfo(retval);
        tmp << msg;
        device->set_state(Tango::FAULT);
        device->set_status(tmp.str());
        return (void*) 0;
    }
    //cerr << "Holding thread terminating\n";
    return (void*) 0;
}
