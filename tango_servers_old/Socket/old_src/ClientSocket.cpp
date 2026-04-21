//============================================================
// 
// file: ClientSocket.cpp
//
// description: From an article in "Linux gazette" by Rob Tougher
//              Implementation of the ClientSocket class.
//              And modified later.
//
// project :      TANGO Device Server.
//
// $Author: pascal_verdier $
//
// $Revision: 1.2 $
// $Log: ClientSocket.cpp,v $
// Revision 1.2  2009/06/18 09:07:07  pascal_verdier
// Converted to Device_4Impl class.
// Errors and reconnection have been improved.
//
// Revision 1.1.1.1  2007/01/12 10:07:43  pascal_verdier
// Initial Revision
//
//
// copyleft :     European Synchrotron Radiation Facility
//                BP 220, Grenoble 38043
//                FRANCE
//
//         (c) - Software Engineering Group - ESRF
//=============================================================================




//#include <iostream>
//#include <string>
#include <tango.h>
#include "ClientSocket.h"
#include "SocketException.h"

using namespace std;

#ifdef TRACE_TIME
#	include <sys/time.h>

#ifndef	TIME_VAR
#	ifndef WIN32

#		define	TimeVal	struct timeval
#		define	GetTime(t)	gettimeofday(&t, NULL);
#		define	Elapsed(before, after)	\
			1000.0*(after.tv_sec-before.tv_sec) + \
			((double)after.tv_usec-before.tv_usec) / 1000

#	else

#		define	TimeVal	struct _timeb
#		define	GetTime(t)	_ftime(&t);
#		define	Elapsed(before, after)	\
			1000*(after.time - before.time) + (after.millitm - before.millitm)

#	endif	/*	WIN32		*/
#endif	/*	TIME_VAR	*/
#endif	/*	TRACE_TIME	*/

//------------------------------------------------------------
/**
 *	ClientSocket constructor
 */
//------------------------------------------------------------
ClientSocket::ClientSocket(std::string host, int port)
{
	if (! SocketAccess::create())
	{
		throw SocketException ("Cannot create client socket.");
	}

	if (! SocketAccess::connect (host, port))
	{
 		TangoSys_MemStream	tms;
 		tms << "Cannot connect to " << host << ":" << port;
		throw SocketException (tms.str());
	}
}

//------------------------------------------------------------
/**
 *	ClientSocket operator overload
 */
//------------------------------------------------------------
const ClientSocket& ClientSocket::operator << (const std::string& s) const
{
	if (! SocketAccess::send(s))
	{
		throw SocketException ("Write Socket Failed.");
	}

	return *this;

}

//------------------------------------------------------------
/**
 *	ClientSocket operator overload
 */
//------------------------------------------------------------
const ClientSocket& ClientSocket::operator >> (std::string& s) const
{
	if (SocketAccess::recv(s) == 0)
	{
		throw SocketException ("Read Socket Failed.");
	}

	return *this;
}

//------------------------------------------------------------
/**
 *	ClientSocket set non blocking state
 */
//------------------------------------------------------------
void ClientSocket::set_non_blocking(const bool b)
{
	SocketAccess::set_non_blocking (b);
}

//------------------------------------------------------------
/**
 *	ClientSocket read line (until '\n')
 */
//------------------------------------------------------------
void ClientSocket::readln(std::string& s, short timeout)
{
	string	buf("");
	char	c = 0;

	while(c != '\n')
	{
		readchar(c, timeout);
		buf += c;
	}

	s = buf;
}
//------------------------------------------------------------
/**
 *	ClientSocket read until terminator received
 */
//------------------------------------------------------------
void ClientSocket::readuntil(std::string& s, char *terminator, short timeout)
{
	string	buff("");
	string	s_term(terminator);
	int		nb = 0;
	int		term_len = strlen(terminator);
	char	term_last_char = terminator[term_len-1];
	char 	c;
	bool	found = false;
	while (!found)
	{
		readchar(c, timeout);	// Try to get a char.
		//	OK add to buffer
		buff += c;
		nb++;
		if (c==term_last_char  &&  nb>term_len)	//	Check with terminator
		{
			//	get the end of buffer.
			string::size_type	pos = nb - term_len;
			string	s = buff.substr(pos, nb);
			//	compare with terminator
			found = (s == s_term);
		}
	}
	s = buff;
}

//------------------------------------------------------------
/**
 *	ClientSocket read char with a timeout
 */
//------------------------------------------------------------
void ClientSocket::readchar(char &c, short timeout)
{
#ifdef TRACE_TIME
	TimeVal	t0;
	TimeVal	t1;
	GetTime(t0);
#endif
	int	status = SocketAccess::recv(c, timeout);
#ifdef TRACE_TIME
	GetTime(t1);
	double	dt = Elapsed(t0, t1);
	if (dt>0.5*timeout)
		cout << "read socket returns "<< status <<" in " <<
			 dt << " ms	errno: " << errno << endl;
#endif
	/*
		TangoSys_MemStream	tms1;
		tms1 << "status:	" << status;
		cout <<	tms1.str() << endl;
	*/
	if (status==1)
		return;	//	Ok on char read
	else
		throw SocketException ("Read Socket Failed");

}
