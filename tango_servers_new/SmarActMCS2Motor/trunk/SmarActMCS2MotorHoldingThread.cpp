#include <SmarActMCS2MotorHoldingThread.h>
using namespace std;
#include <SmarActControlConstants.h>
SmarActMCS2MotorHoldingThread::SmarActMCS2MotorHoldingThread(string& devname)
    : device_name(devname)
{
    
    start_undetached();
}

void* SmarActMCS2MotorHoldingThread::run_undetached(void* ptr)
{

    device = new Tango::DeviceProxy(device_name);
    Tango::DeviceAttribute moveMode("MoveMode", Tango::DevLong(SA_CTL_MOVE_MODE_SCAN_ABSOLUTE));
    device->write_attribute(moveMode);
    
    Tango::DeviceAttribute position("Position", Tango::DevDouble(0));
    device->write_attribute(position);
    
    waitForOnState();


    position << Tango::DevDouble(35000);
    device->write_attribute(position);

    
    waitForOnState();
    
    moveMode << Tango::DevLong(SA_CTL_MOVE_MODE_CL_RELATIVE);
    device->write_attribute(moveMode);
    
    position << Tango::DevDouble(0);
    device->write_attribute(position);

    return (void*) 0;
}

void SmarActMCS2MotorHoldingThread::waitForOnState()
{
    for(;;)
    {
        usleep(20000);
        Tango::DevState dev_state = device->state();
        if(dev_state == Tango::ON)
        {
            break;
        }
    }
}
