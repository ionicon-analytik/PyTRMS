# --------------------------------------------- 
# makefile for compiling Python projects poetry
#
#   This Makefile is executed with the nmake program
#   found in the VisualStudio developer tools:
#   C:\Program Files (x86)\Microsoft Visual Studio\2017\Community\VC\Tools\MSVC\14.15.26726\bin\Hostx86\x86\nmake.exe
#
#   Add to your PATH and run it with
#   >>> nmake /nologo <target>
#
# ---------------------------------------------

!IFNDEF TARGET
TARGET=pytrms
!ENDIF


# !IFNDEF DIST
# DIST=$(BUILDDIR)\dist
# !ENDIF

# !IFNDEF TESTREPORTDIR
# TESTREPORTDIR=$(BUILDDIR)\testreports
# !ENDIF


!IFNDEF PYTHON
PYTHON=poetry run python
!ENDIF

# PYTEST=$(PYTHON) -m pytest
# PYTEST_FLAGS=#--html=report.html --self-contained-html

# copy: unittest wheel tree
	# :: copying files to distribution dir @ $(DIST)...
	# copy /y $(MAKEDIR)\dist\*.whl $(DIST)

all: wheel
	

wheel: bdist_wheel
	

bdist_wheel: icapi.cp38-win_amd64.pyd
	:: building package $(TARGET)...
	poetry build

ext: icapi.cp38-win_amd64.pyd
	

icapi.cp38-win_amd64.pyd: src/icapimodule.c
	:: building package $(TARGET)...
	:: $(PYTHON) setup.py $@
	poetry run python build.py build_ext

unittest: tree
	:: descending into directory .\test...
	@cd test
	$(PYTEST) . $(PYTEST_FLAGS)
	:: moving testreports...
	@move report.html $(TESTREPORTDIR)\$(TARGET)_unittest.html
	:: leaving directory $(TARGET)\test...
	@cd $(MAKEDIR)

doctest: tree
	$(PYTEST) --doctest-modules $(PYTEST_FLAGS) $(TARGET)
	:: moving testreports...
	move report.html $(TESTREPORTDIR)\$(TARGET)_doctest.html



.IGNORE:
docu: doc\uml\$(TARGET).png
	:: descending into directory .\doc...
	@cd $(MAKEDIR)\doc
	:: running sphinx compiler...
	.\make.bat html
	:: leaving directory $(TARGET)\doc...
	@cd $(MAKEDIR)

clean:
	rd /S /Q $(TARGET).egg-info
	rd /S /Q build
	rd /S /Q dist

cleanall: clean
	:: removing testreports...
	del report.html
	del test\report.html
	:: removing __pycache__ ...
	rd /S /Q __pycache__
	rd /S /Q $(TARGET)\__pycache__
	:: descending into directory $(TARGET)\doc...
	@cd doc
	rd /S /Q _build
	del uml\$(TARGET).png
	:: leaving directory $(TARGET)\doc...
	@cd $(MAKEDIR)

help:
	@echo possible commands:
	@echo copy
	@echo bdist_wheel (wheel)
	@echo sdist
	@echo develop
	@echo qt
	@echo unittest
	@echo doctest
	@echo docu
	@echo clean
	@echo cleanall

