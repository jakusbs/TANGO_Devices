#include <iostream>
#include <string>
#include <MCSControl.h>


using namespace std;

int main(int argc, char** argv)
{
    string locator("network:192.168.132.90");
	SA_INDEX handle;
	SA_STATUS retval;

    if((retval = SA_OpenSystem(&handle, locator.c_str(), "")) != SA_OK)
	{
		const char* tmp;
        SA_GetStatusInfo(retval, &tmp);
        cerr << "Retval: " << retval << " " << tmp << endl;
        exit(255);
    }
    if((retval = SA_CloseSystem(handle)) != SA_OK)
	{
		const char* tmp;
		SA_GetStatusInfo(retval, &tmp);
	}
    exit(0);
}




    
