//=============================================================================
//
// file :        ClientSocket.h
//
// description : Definition of the ClientSocket class.
//               From an article in "Linux gazette" by Rob Tougher
//               And modified later.
//
// project :	Socket
//
// $Author: pascal_verdier $
//
// $Revision: 1.1.1.1 $
// $Log: ClientSocket.h,v $
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

#ifndef ClientSocket_class
#define ClientSocket_class

#include <string>
#include "SocketAccess.h"


#include <sys/time.h>


class ClientSocket : private SocketAccess
{
 public:
  ClientSocket ( std::string host, int port );
  virtual ~ClientSocket(){};

  void set_non_blocking(const bool);

  const ClientSocket& operator << ( const std::string& ) const;
  const ClientSocket& operator >> ( std::string& ) const;
  void readln(std::string&, short);
  void readuntil(std::string&, char *, short);
  void readchar(char &, short);
};

#endif
