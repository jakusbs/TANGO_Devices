#include <iostream>
#include <string>
#include <SmarActControlConstants.h>
#include <SmarActControl.h>

using namespace std;

int main(int argc, char** argv)
{
    SA_CTL_DeviceHandle_t hn;
    SA_CTL_Result_t result;
    string locator("network:192.168.132.90:55550");

    result = SA_CTL_Open(&hn, locator.c_str(), "");
    if (result != SA_CTL_ERROR_NONE)
    {
        cerr << "Open error on " << locator << " " << SA_CTL_GetResultInfo(result) << endl;
        SA_CTL_Close(hn);
        exit(255);
    }

    char deviceSN[SA_CTL_STRING_MAX_LENGTH];
    size_t ioStringSize = sizeof(deviceSN);

    result = SA_CTL_GetProperty_s(hn, 0, SA_CTL_PKEY_DEVICE_SERIAL_NUMBER, deviceSN, &ioStringSize);
    if (result != SA_CTL_ERROR_NONE)
    {
        cerr << "Read error on serial number: " << SA_CTL_GetResultInfo(result) << endl;
        SA_CTL_Close(hn);
        exit(255);
    }
    cerr << "Serial number: " << deviceSN << endl;

    /*int32_t fwVersion[4];
    size_t ioArraySize = 4;
    result = SA_CTL_GetProperty_i32(hn, 0,SA_CTL_PKEY_FIRMWARE_VERSION,fwVersion,&ioArraySize);
    if (result != SA_CTL_ERROR_NONE)
    {
        cerr << "Read error on firmware version: " << SA_CTL_GetResultInfo(result) << endl;
        SA_CTL_Close(hn);
        exit(255);
    }
    cerr << "Firmware release: " << fwVersion[0] << "." << fwVersion[1] << "."  << fwVersion[2] << "."  << fwVersion[3] << "."  << endl;*/

    int32_t noOfchannels;

    result = SA_CTL_GetProperty_i32(hn, 0,  SA_CTL_PKEY_NUMBER_OF_CHANNELS, &noOfchannels, 0);
    if (result != SA_CTL_ERROR_NONE)
    {
        cerr << "Read error on number of channels: " << SA_CTL_GetResultInfo(result) << endl;
        SA_CTL_Close(hn);
        exit(255);
    }
    cerr << "Number of channels: " <<  noOfchannels << endl;
    

    for (int8_t channel = 0; channel < noOfchannels; channel++)
    {
        int32_t state;
        result = SA_CTL_GetProperty_i32(hn, channel, SA_CTL_PKEY_CHANNEL_STATE, &state, 0);
        if (result != SA_CTL_ERROR_NONE)
        {
            cerr << "Read error on state of channel " << int32_t(channel) << ": " << SA_CTL_GetResultInfo(result) << endl;
            SA_CTL_Close(hn);
            exit(255);
        }
        cerr << "Channel " << int32_t(channel) << " moving state:   " << hex << ((state & SA_CTL_CH_STATE_BIT_ACTIVELY_MOVING) ? "1" : "0") << dec << endl;
        cerr << "Channel " << int32_t(channel) << " sensor present: " << hex << ((state & SA_CTL_CH_STATE_BIT_SENSOR_PRESENT)  ? "1" : "0") << dec << endl;
        cerr << "Channel " << int32_t(channel) << " reference mark: " << hex << ((state & SA_CTL_CH_STATE_BIT_REFERENCE_MARK)  ? "1" : "0") << dec << endl; 
        if(state & SA_CTL_CH_STATE_BIT_SENSOR_PRESENT)
        {
            cerr << "Channel " << int32_t(channel) << " is referenced:  " << hex << ((state & SA_CTL_CH_STATE_BIT_IS_REFERENCED) ? "1" : "0") << dec << endl;
            int32_t baseUnit;
            result = SA_CTL_GetProperty_i32(hn, channel, SA_CTL_PKEY_POS_BASE_UNIT, &baseUnit, 0);
            if (result != SA_CTL_ERROR_NONE)
            {
                cerr << "Read error on base unit of channel " << int32_t(channel) << SA_CTL_GetResultInfo(result) << endl;
                SA_CTL_Close(hn);
                exit(255);
            }
            cerr << "Channel positioner type of channel " << int32_t(channel) << ": " << (baseUnit == SA_CTL_UNIT_METER ? " linear" : " rotary") << endl;
            int32_t ptype;
            result = SA_CTL_GetProperty_i32(hn, channel, SA_CTL_PKEY_POSITIONER_TYPE, &ptype, 0);
            if (result != SA_CTL_ERROR_NONE)
            {
                cerr << "Read error on positioner type of channel " << int32_t(channel) << SA_CTL_GetResultInfo(result) << endl;
                SA_CTL_Close(hn);
                exit(255);
            }
            cerr << "Channel positioner type of channel " << int32_t(channel) << ": " << ptype << endl;
            char name[SA_CTL_STRING_MAX_LENGTH];
            ioStringSize = sizeof(name);
            result = SA_CTL_GetProperty_s(hn, 0, SA_CTL_PKEY_POSITIONER_TYPE_NAME, name, &ioStringSize);
            if (result != SA_CTL_ERROR_NONE)
            {
                cerr << "Read error on positioner name of channel " << int32_t(channel) << SA_CTL_GetResultInfo(result) << endl;
                SA_CTL_Close(hn);
                exit(255);
            }
            cerr << "Channel positioner name of channel " << int32_t(channel) << ": " << name << endl;
            int64_t limit;
            result = SA_CTL_GetProperty_i64(hn, 0, SA_CTL_PKEY_RANGE_LIMIT_MIN, &limit, 0);
            if (result != SA_CTL_ERROR_NONE)
            {
                cerr << "Read error on min limit of channel " << int32_t(channel) << SA_CTL_GetResultInfo(result) << endl;
                SA_CTL_Close(hn);
                exit(255);
            }
            cerr << "Min limit of channel " << int32_t(channel) << ": " << limit << endl;
            result = SA_CTL_GetProperty_i64(hn, 0, SA_CTL_PKEY_RANGE_LIMIT_MAX, &limit, 0);
            if (result != SA_CTL_ERROR_NONE)
            {
                cerr << "Read error on min limit of channel " << int32_t(channel) << SA_CTL_GetResultInfo(result) << endl;
                SA_CTL_Close(hn);
                exit(255);
            }
            cerr << "Max limit of channel " << int32_t(channel) << ": " << limit << endl;
            cerr << endl;
        }
    }


    SA_CTL_Close(hn);

    exit(0);
}
