//=============================================================================
//
// file :        SocketAccess.h
//
// description : Definition of the SocketAccess class.
//               From an article in "Linux gazette" by Rob Tougher
//               And modified later.
//
// project :	Socket
//
// $Author: pascal_verdier $
//
// $Revision: 1.1.1.1 $
// $Log: SocketAccess.h,v $
// Revision 1.1.1.1  2007/01/12 10:07:43  pascal_verdier
// Initial Revision
//
//
// copyleft :    European Synchrotron Radiation Facility
//               BP 220, Grenoble 38043
//               FRANCE
//
//         (c) - Software Engineering Group - ESRF
//=============================================================================

#ifndef Socket_access
#define Socket_access

#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <netdb.h>
#include <unistd.h>
#include <string>
#include <arpa/inet.h>

const int MAXHOSTNAME = 200;
const int MAXCONNECTIONS = 5;
const int MAXRECV = 500;

class SocketAccess
{
 public:
  SocketAccess();
  virtual ~SocketAccess();

  // Server initialization
  bool create();
  bool bind ( const int port );
  bool listen() const;
  bool accept ( SocketAccess& ) const;

  // Client initialization
  bool connect ( const std::string host, const int port );

  // Data Transimission
  bool send ( const std::string ) const;
  int recv ( std::string& ) const;
  int recv (char& c, int timout_millis) const;


  void set_non_blocking ( const bool );

  bool is_valid() const { return m_sock != -1; }

 private:

  int m_sock;
  sockaddr_in m_addr;
};

#endif
