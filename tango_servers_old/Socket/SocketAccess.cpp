//=============================================================================
// 
// file: SocketAccess.cpp
//
// description: From an article in "Linux gazette" by Rob Tougher
//              Implementation of the SocketAccess class.
//               And modified later.
//
// project :      TANGO Device Server.
//
// $Author: pascal_verdier $
//
// $Revision: 1.1.1.1 $
// $Log: SocketAccess.cpp,v $
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

#include "SocketAccess.h"
#include "string.h"
#include <string.h>
#include <errno.h>
#include <fcntl.h>
#include <netinet/tcp.h>
#include <stdio.h>
#include <stdlib.h>

#include <iostream>
using namespace std;

//------------------------------------------------------------
//------------------------------------------------------------
SocketAccess::SocketAccess():m_sock(-1)
{
  memset(&m_addr, 0, sizeof (m_addr));
}

//------------------------------------------------------------
//------------------------------------------------------------
SocketAccess::~SocketAccess()
{
  if (is_valid())
    {
      ::close (m_sock);
      // cout << "Closed!" << endl;
    }
}

//------------------------------------------------------------
//------------------------------------------------------------
bool SocketAccess::create()
{
  m_sock = socket(AF_INET, SOCK_STREAM, 0);

  if (! is_valid())
    return false;  

  // TIME_WAIT - argh
  int on = 1;
  if ( setsockopt (m_sock, SOL_SOCKET, SO_REUSEADDR, 
		   (const char*) &on, sizeof (on)) == -1)
    return false;

  int flag = 1, ret;
  struct protoent *p;
  p = getprotobyname("tcp");
  ret = setsockopt( m_sock, p->p_proto, TCP_NODELAY, (char *)&flag, sizeof(flag) );

  return true;
}

//------------------------------------------------------------
//------------------------------------------------------------
bool SocketAccess::bind ( const int port )
{
  if (! is_valid())
    {
      return false;
    }

  m_addr.sin_family = AF_INET;
  m_addr.sin_addr.s_addr = INADDR_ANY;
  m_addr.sin_port = htons (port);

  int bind_return = ::bind(m_sock, (struct sockaddr *) &m_addr,
			   sizeof (m_addr));

  if (bind_return == -1)
    {
      return false;
    }
  
  return true;
}

//------------------------------------------------------------
//------------------------------------------------------------
bool SocketAccess::listen() const
{
  if (! is_valid())
    {
      return false;
    }

  int listen_return = ::listen(m_sock, MAXCONNECTIONS);
  
  if (listen_return == -1)
    {
      return false;
    }
  
  return true;
}

//------------------------------------------------------------
//------------------------------------------------------------
bool SocketAccess::accept (SocketAccess& new_socket) const
{
  int addr_length = sizeof (m_addr);
  new_socket.m_sock = ::accept (m_sock,
				(sockaddr *) &m_addr,
				(socklen_t *) &addr_length);
  
  if (new_socket.m_sock <= 0)
    return false;
  else
    return true;
}

//------------------------------------------------------------
//------------------------------------------------------------
bool SocketAccess::send (const std::string s) const
{
  int status = ::send(m_sock, s.c_str(), s.size(), MSG_NOSIGNAL);
  if (status == -1)
    {
      return false;
    }
  else
    {
      return true;
    }
}

//------------------------------------------------------------
//------------------------------------------------------------
int SocketAccess::recv (std::string& s) const
{
  char buf [ MAXRECV + 1 ];

  s = "";

  memset (buf, 0, MAXRECV + 1);

  int status = ::recv (m_sock, buf, MAXRECV, 0);

  if (status == -1)
    {
#ifdef EBUG
      cout << "status == -1   errno == " << errno << "  in SocketAccess::recv" << endl;
#endif
      return 0;
    }
  else if (status == 0)
    {
#ifdef EBUG
      cout << "status == -1   errno == " << errno << "  in SocketAccess::recv" << endl;
#endif
      return 0;
    }
  else
    {
      s = buf;
      return status;
    }
}

//------------------------------------------------------------
//------------------------------------------------------------
int SocketAccess::recv (char& c, int timout_millis) const
{
	//	Build timeout
	struct timeval  tv ;
	tv.tv_sec  = timout_millis/1000;
	tv.tv_usec = (timout_millis - tv.tv_sec * 1000) * 1000 ;
	
	// Set up the file descriptor set.
	fd_set	fds;
	FD_ZERO(&fds) ;
	FD_SET(m_sock, &fds) ;

	//	Wait until timeout or data received.
	int status = ::select(m_sock+1, &fds, NULL, NULL, &tv);
	if (status<0)
		return -1;

	//	If not timeout, read sockect
	return ::recv (m_sock, &c, 1, 0);
}



//------------------------------------------------------------
//------------------------------------------------------------
bool SocketAccess::connect(const std::string host, const int port)
{
  if (! is_valid()) return false;

  m_addr.sin_family = AF_INET;
  m_addr.sin_port = htons (port);
  
  struct hostent *hostinfo;
  hostinfo = gethostbyname (host.c_str());
  if (hostinfo == NULL) 
    {
      printf ("Unknown host %s.\n", host.c_str());
      exit (EXIT_FAILURE);
    }
   bcopy(hostinfo->h_addr, &m_addr.sin_addr, hostinfo->h_length);

   /*---------------------------------------------------------
      Standard Linux connect timeout is more than 4 minutes !

      What I do to improve the connect:

      - Set socket to non blocking mode.
      - The first connect returns immediately with status -1 
      and errno set to EINPROGRESS.
      - Loop for 5 times, calling connect which returns 
      status 0 if the connection is successfull or returns -1 
      and errno set to EINPROGRESS if the connection is not yet 
      established.
   */

   int opts;
   opts = fcntl (m_sock, F_GETFL);
   if (opts >= 0)
     opts = (opts | O_NONBLOCK);
   fcntl (m_sock, F_SETFL, opts);
  
  int status;
  status = ::connect (m_sock, (sockaddr *) &m_addr, sizeof (m_addr));
#ifdef EBUG
  cout << "STATUS: " << status << "***> " << strerror(errno) << endl;
#endif

  if(status != 0)  // We are not connected
    {
      if(errno == EINPROGRESS) // But the connection is in progress
	{
	  int nb = 0;
	  struct timespec time_to_sleep, time_remaining;

	  while(nb++ < 5) // We will attempt to connect every 100 ms for 5 times max.
	    {
	      status = ::connect (m_sock, (sockaddr *) &m_addr, sizeof (m_addr));
#ifdef EBUG
	      cout << "STATUS: " << status << "***> " << strerror(errno) << endl;
#endif
	      if(status != 0) // Still not connected
		{
		  if(errno == EALREADY) // This is the right error !
		    {
		      time_to_sleep.tv_sec = 0;
		      time_to_sleep.tv_nsec = 100000000L;
		      nanosleep(&time_to_sleep, &time_remaining);  // Sleep for 100 ms
		    }
		}
	      else
		return true; // Connection is OK.
	    }
	  return false; // Too much attempts, so failure !
	}
      else
	return false; // Not the right error, so failure !
    }
  else
    return true; // Connected at first attempt !
}

//------------------------------------------------------------
//------------------------------------------------------------
void SocketAccess::set_non_blocking(const bool b)
{
  int opts;
  
  opts = fcntl (m_sock, F_GETFL);
  
  if (opts < 0)
    {
      return;
    }
  
  if ( b )
    opts = (opts | O_NONBLOCK);
  else
    opts = (opts & ~O_NONBLOCK);
  
  fcntl (m_sock, F_SETFL, opts);
}
