#include <SmarActMCS2CtrlTrajectoryThread.h>

SmarActMCS2CtrlTrajectoryThread::SmarActMCS2CtrlTrajectoryThread(SmarActMCS2Ctrl_ns::SmarActMCS2Ctrl& dev, SA_CTL_DeviceHandle_t handle, deque <StreamTargetPtrVector>& trajectoryTargetQueue, Tango::DevLong& triggerMode, bool& stop, bool& terminate, omni_condition* startCondition)
 :  _device(dev), _handle(handle), _trajectoryTargetQueue(trajectoryTargetQueue), _triggerMode(triggerMode), _stop(stop), _terminate(terminate),  _startCondition(startCondition)
{
	start_undetached();
}

void* SmarActMCS2CtrlTrajectoryThread::run_undetached(void* ptr)
{
	SA_CTL_Result_t result;
	for(;;)
	{
		_startCondition->wait();
		if(_terminate)
		{
			break;
		}
		if(_stop)
		{
			continue;
		}
		_device.trajectoryActive(true);
		_trajectoryAbort = false;
		if(!waitForStart(_trajectoryTargetQueue.front()))
		{
			continue;
		}
		if((result = SA_CTL_OpenStream(_handle, &_streamHandle, _triggerMode)) != SA_CTL_ERROR_NONE)
		{
			_device.set_state(Tango::FAULT);
			_device.set_status(SA_CTL_GetResultInfo(result));
			_device.positionersReset();
			continue;
		}
		while(_trajectoryTargetQueue.size() > 0)
		{
			auto line = _trajectoryTargetQueue.front();
			vector<uint8_t> frame;
 			for(auto it = line->begin(); it != line->end(); ++it)
 			{
				frame.insert(frame.end(), (*it)->channelData(), (*it)->channelData() + sizeof((*it)->channel())); 
				frame.insert(frame.end(), (*it)->positionData(), (*it)->positionData() + sizeof((*it)->position()));
 			}
			result = SA_CTL_StreamFrame(_handle, _streamHandle, frame.data(), frame.size());
			if(result != SA_CTL_ERROR_NONE && result != SA_CTL_ERROR_ABORTED)
			{
				_device.set_state(Tango::FAULT);
				_device.set_status(SA_CTL_GetResultInfo(result));
				_stop = true;
				_trajectoryAbort = true;
				break;
			}
			if(result == SA_CTL_ERROR_ABORTED)
			{
				_trajectoryAbort = true;
				break;
			}
			_trajectoryTargetQueue.pop_front();
		}
		if(!_trajectoryAbort)
		{
			result = SA_CTL_CloseStream(_handle, _streamHandle);
			if(result != SA_CTL_ERROR_NONE)
			{
				_device.set_state(Tango::FAULT);
				_device.set_status(SA_CTL_GetResultInfo(result));
			}
		}
		while(_trajectoryTargetQueue.size() > 0) // just in case we were aborted
		{
			_trajectoryTargetQueue.pop_front();
		}
	}
	return (void*) NULL;
}

void SmarActMCS2CtrlTrajectoryThread::abortStreaming()
{
	if(_device.streamStarted()) // are we running a stream at all ?
	{
		SA_CTL_Result_t result;
		if( (result = SA_CTL_AbortStream(_handle, _streamHandle)) !=  SA_CTL_ERROR_NONE)
		{
			_device.set_state(Tango::FAULT);
			_device.set_status(SA_CTL_GetResultInfo(result));
    	}
		_trajectoryAbort = true;
	}
}

// we cannot start streaming before all participating axes reached their start positions
bool SmarActMCS2CtrlTrajectoryThread::waitForStart(StreamTargetPtrVector& firstLine)
{
	bool retval = true;
	for(auto it = firstLine->begin(); it != firstLine->end(); ++it)
	{
		for(;;)
		{
			Tango::DevUShort mstate = _device.axis_state((*it)->channel());
			if((mstate & SA_CTL_CH_STATE_BIT_ACTIVELY_MOVING))
			{
				usleep(5000);
				continue;
			}
			else if((mstate & SA_CTL_CH_STATE_BIT_END_STOP_REACHED))
			{
				stringstream tmp;
				tmp << "Can not start streaming, axis " << (int) (*it)->channel() << " is at limit switch" << endl;
				_device.positionersReset();
				_device.set_state(Tango::FAULT);
				_device.set_status(tmp.str());
				retval = false;
				break;
			}
			else
			{
				break;
			}
		}
	}
	return retval;
}
