#include <SmarActMCS2CtrlEventThread.h>

SmarActMCS2CtrlEventThread::SmarActMCS2CtrlEventThread(SmarActMCS2Ctrl_ns::SmarActMCS2Ctrl& dev, SA_CTL_DeviceHandle_t handle, Tango::DevBoolean ttydebug)
    : device(dev), hn(handle),  _ttydebug(ttydebug) 
{
    
    start_undetached();
}

void* SmarActMCS2CtrlEventThread::run_undetached(void* ptr)
{
    SA_CTL_Event_t  event;
    SA_CTL_Result_t retval;
    for(;;)
    {
        
        retval = SA_CTL_WaitForEvent(hn, &event,SA_CTL_INFINITE);
        if(retval == SA_CTL_ERROR_CANCELED)
        {
			if(_ttydebug)
			{
				cerr << "Event thread cancelled\n";
			}
            break;
        }
        else if(retval == SA_CTL_ERROR_NONE)
        {
			switch(event.type)
			{
				case SA_CTL_EVENT_STREAM_FINISHED:
					if(_ttydebug)
					{
						cerr << "Received SA_CTL_EVENT_STREAM_FINISHED\n";
					}
					if(SA_CTL_EVENT_PARAM_RESULT(event.i32) == SA_CTL_ERROR_NONE)
					{
						if(_ttydebug)
						{
							cerr << "All frames processed\n";
						}
						// All streaming frames were processed, stream finished.
					}
					else if (SA_CTL_EVENT_PARAM_RESULT(event.i32) == SA_CTL_ERROR_ABORTED)
					{
						// Stream was canceled by the user.
						if(_ttydebug)
						{
							cerr << "Streaming canceled by user\n";
						}
					}
					else
					{
						// Stream was canceled by device
						if(_ttydebug)
						{
							cerr << "Streaming canceled by device\n";
						}
					}
					device.streamStarted(false);
					device.positionersReset();
					device.trajectoryActive(false);
				break;
				case SA_CTL_EVENT_STREAM_READY:
					if(_ttydebug)
					{
						cerr << "Received SA_CTL_EVENT_STREAM_READY\n";
					}
					device.streamReady(true);
					
				break;
                case SA_CTL_EVENT_STREAM_TRIGGERED:
					if(_ttydebug)
					{
						cerr << "Received SA_CTL_EVENT_STREAM_TRIGGERED\n";
					}
					device.streamStarted(true);
					device.streamReady(false);
				break;
				default:
				if(_ttydebug)
            	{
               		cerr << "Event: " << SA_CTL_GetEventInfo(&event) << endl;
            	}
			}
            device.updateEventState(event.idx, event.type, event.i32);
		}
        else
        {
            device.set_state(Tango::FAULT);
            device.set_status(SA_CTL_GetResultInfo(retval));
            if(_ttydebug)
            {
                cerr << "Event thread: " << SA_CTL_GetResultInfo(retval) << endl;
            }
        }
    }
	if(_ttydebug)
	{
		cerr << "Event thread teminates\n";
	}
    return (void*) 0;
}
