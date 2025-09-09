cmake_minimum_required(VERSION 3.18 FATAL_ERROR)
cmake_policy(VERSION ${CMAKE_MAJOR_VERSION}.${CMAKE_MINOR_VERSION})
project(apertium-get
	VERSION 1.0.2
	LANGUAGES NONE
	)

option(BUILD_MAN "Set to ON to build man page" OFF)

include(GNUInstallDirs)

if(BUILD_MAN)
	add_custom_target(man ALL COMMAND ./help2man.sh ${PROJECT_VERSION})
endif()

install(PROGRAMS
	"${CMAKE_CURRENT_SOURCE_DIR}/apertium-get.py"
	DESTINATION ${CMAKE_INSTALL_BINDIR}
	RENAME apertium-get)

install(FILES "apertium-get.1"
	DESTINATION ${CMAKE_INSTALL_MANDIR}/man1)
