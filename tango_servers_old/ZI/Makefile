SCAN_PLUGIN_DIR = $(shell pkg-config --variable=prefix scansl)/share/ScanUtils/plugins/timebase/

SCAN_PLUGIN_SHLIB_NAME = libPlugins.Timebase.ZI.py
SCAN_PLUGIN_CPP_NAME = ZI.py


CXXFLAGS += $(shell pkg-config --cflags yat)
CXXFLAGS += $(shell pkg-config --cflags yat4tango)
CXXFLAGS += $(shell pkg-config --cflags tango)
CXXFLAGS += $(shell pkg-config --cflags scansl)


CXX := c++
CXXFLAGS += -O2 -fPIC



$(SCAN_PLUGIN_SHLIB_NAME).so: $(SCAN_PLUGIN_CPP_NAME).o
	$(CXX) -shared $(SCAN_PLUGIN_CPP_NAME).o -o $(SCAN_PLUGIN_SHLIB_NAME).so

    
actuator_template.o:
	$(CXX) $(CXXFLAGS) -fpic -c $(SCAN_PLUGIN_CPP_NAME).cpp -o $(SCAN_PLUGIN_CPP_NAME).o

all: $(SCAN_PLUGIN_SHLIB_NAME).so

install: $(SCAN_PLUGIN_SHLIB_NAME).so
	cp $(SCAN_PLUGIN_SHLIB_NAME).so $(SCAN_PLUGIN_DIR)

clean:
	rm -f $(SCAN_PLUGIN_SHLIB_NAME).so
	rm -f $(SCAN_PLUGIN_CPP_NAME).o

uninstall:
	rm $(SCAN_PLUGIN_DIR)/$(SCAN_PLUGIN_SHLIB_NAME).so

