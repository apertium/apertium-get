cmake_minimum_required(VERSION 3.0 FATAL_ERROR)
cmake_policy(VERSION ${CMAKE_MAJOR_VERSION}.${CMAKE_MINOR_VERSION})
project(apertium-get
	VERSION 1.0.0
	LANGUAGES NONE
	)

include(GNUInstallDirs)

install(PROGRAMS
	"${CMAKE_CURRENT_SOURCE_DIR}/apertium-get"
	DESTINATION ${CMAKE_INSTALL_BINDIR})
