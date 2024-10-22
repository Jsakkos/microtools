import czifile as zis
import os
from pathlib import Path
import xmltodict
import numpy as np
from collections import Counter
from lxml import etree as ET
import sys
import dask.array as da
import pandas as pd
import tifffile
import pydash



def get_imgtype(imagefile):
    """Returns the type of the image based on the file extension - no magic

    :param imagefile: filename of the image
    :type imagefile: str
    :return: string specifying the image type
    :rtype: str
    """

    imgtype = None

    if imagefile.lower().endswith('.ome.tiff') or imagefile.lower().endswith('.ome.tif'):
        # it is on OME-TIFF based on the file extension ... :-)
        imgtype = 'ometiff'

    elif imagefile.lower().endswith('.tiff') or imagefile.lower().endswith('.tif'):
        # it is on OME-TIFF based on the file extension ... :-)
        imgtype = 'tiff'

    elif imagefile.lower().endswith('.czi'):
        # it is on CZI based on the file extension ... :-)
        imgtype = 'czi'

    elif imagefile.lower().endswith('.png'):
        # it is on CZI based on the file extension ... :-)
        imgtype = 'png'

    elif imagefile.lower().endswith('.jpg') or imagefile.lower().endswith('.jpeg'):
        # it is on OME-TIFF based on the file extension ... :-)
        imgtype = 'jpg'

    return imgtype


def create_metadata_dict():
    """A Python dictionary will be created to hold the relevant metadata.

    :return: dictionary with keys for the relevant metadata
    :rtype: dict
    """

    metadata = {'Directory': None,
                'Filename': None,
                'Extension': None,
                'ImageType': None,
                'AcqDate': None,
                'TotalSeries': None,
                'SizeX': None,
                'SizeY': None,
                'SizeZ': 1,
                'SizeC': 1,
                'SizeT': 1,
                'SizeS': 1,
                'SizeB': 1,
                'SizeM': 1,
                'Sizes BF': None,
                'DimOrder BF': None,
                'DimOrder BF Array': None,
                'Axes_czifile': None,
                'Shape_czifile': None,
                'czi_isRGB': None,
                'czi_isMosaic': None,
                'ObjNA': [],
                'ObjMag': [],
                'ObjID': [],
                'ObjName': [],
                'ObjImmersion': [],
                'TubelensMag': [],
                'ObjNominalMag': [],
                'XScale': None,
                'YScale': None,
                'ZScale': None,
                'XScaleUnit': None,
                'YScaleUnit': None,
                'ZScaleUnit': None,
                'DetectorModel': [],
                'DetectorName': [],
                'DetectorID': [],
                'DetectorType': [],
                'InstrumentID': [],
                'Channels': [],
                'ChannelNames': [],
                'ChannelColors': [],
                'ImageIDs': [],
                'NumPy.dtype': None
                }

    return metadata

def checkmdscale_none(md, tocheck=['ZScale'], replace=[1.0]):
    """Check scaling entries for None to avoid issues later on

    :param md: original metadata
    :type md: dict
    :param tocheck: list with entries to check for None, defaults to ['ZScale']
    :type tocheck: list, optional
    :param replace: list with values replacing the None, defaults to [1.0]
    :type replace: list, optional
    :return: modified metadata where None entries where replaces by
    :rtype: [type]
    """
    for tc, rv in zip(tocheck, replace):
        if md[tc] is None:
            md[tc] = rv

    return md


def get_metadata_czi(filename, dim2none=False,
                     forceDim=False,
                     forceDimname='SizeC',
                     forceDimvalue=2,
                     convert_scunit=True):
    """
    Returns a dictionary with CZI metadata.

    Information CZI Dimension Characters:
    - '0': 'Sample',  # e.g. RGBA
    - 'X': 'Width',
    - 'Y': 'Height',
    - 'C': 'Channel',
    - 'Z': 'Slice',  # depth
    - 'T': 'Time',
    - 'R': 'Rotation',
    - 'S': 'Scene',  # contiguous regions of interest in a mosaic image
    - 'I': 'Illumination',  # direction
    - 'B': 'Block',  # acquisition
    - 'M': 'Mosaic',  # index of tile for compositing a scene
    - 'H': 'Phase',  # e.g. Airy detector fibers
    - 'V': 'View',  # e.g. for SPIM

    :param filename: filename of the CZI image
    :type filename: str
    :param dim2none: option to set non-existing dimension to None, defaults to False
    :type dim2none: bool, optional
    :param forceDim: option to force to not read certain dimensions, defaults to False
    :type forceDim: bool, optional
    :param forceDimname: name of the dimension not to read, defaults to SizeC
    :type forceDimname: str, optional
    :param forceDimvalue: index of the dimension not to read, defaults to 2
    :type forceDimvalue: int, optional
    :param convert_scunit: convert scale unit string from 'µm' to 'micron', defaults to False
    :type convert_scunit: bool, optional
    :return: metadata - dictionary with the relevant CZI metainformation
    :rtype: dict
    """

    # get CZI object
    czi = zis.CziFile(filename)

    # parse the XML into a dictionary
    metadatadict_czi = czi.metadata(raw=False)

    # initialize metadata dictionary
    metadata = create_metadata_dict()

    # get directory and filename etc.
    metadata['Directory'] = os.path.dirname(filename)
    metadata['Filename'] = os.path.basename(filename)
    metadata['Extension'] = 'czi'
    metadata['ImageType'] = 'czi'

    # add axes and shape information using czifile package
    metadata['Axes_czifile'] = czi.axes
    metadata['Shape_czifile'] = czi.shape

    # determine pixel type for CZI array
    metadata['NumPy.dtype'] = czi.dtype

    # check if the CZI image is an RGB image depending
    # on the last dimension entry of axes
    if czi.shape[-1] == 3:
        metadata['czi_isRGB'] = True

    try:
        metadata['PixelType'] = metadatadict_czi['ImageDocument']['Metadata']['Information']['Image']['PixelType']
    except KeyError as e:
        print('Key not found:', e)
        metadata['PixelType'] = None
    try:
        metadata['SizeX'] = np.int(metadatadict_czi['ImageDocument']['Metadata']['Information']['Image']['SizeX'])
    except KeyError as e:
        metadata['SizeX'] = None
    try:
        metadata['SizeY'] = np.int(metadatadict_czi['ImageDocument']['Metadata']['Information']['Image']['SizeY'])
    except KeyError as e:
        metadata['SizeY'] = None

    try:
        metadata['SizeZ'] = np.int(metadatadict_czi['ImageDocument']['Metadata']['Information']['Image']['SizeZ'])
    except Exception as e:
        # print('Exception:', e)
        if dim2none:
            metadata['SizeZ'] = None
        if not dim2none:
            metadata['SizeZ'] = 1

    # for special cases do not read the SizeC from the metadata
    if forceDim and forceDimname == 'SizeC':
        metadata[forceDimname] = forceDimvalue

    if not forceDim:

        try:
            metadata['SizeC'] = np.int(metadatadict_czi['ImageDocument']['Metadata']['Information']['Image']['SizeC'])
        except Exception as e:
            # print('Exception:', e)
            if dim2none:
                metadata['SizeC'] = None
            if not dim2none:
                metadata['SizeC'] = 1

    # create empty lists for channel related information
    channels = []
    channels_names = []
    channels_colors = []

    # in case of only one channel
    if metadata['SizeC'] == 1:
        # get name for dye
        try:
            channels.append(metadatadict_czi['ImageDocument']['Metadata']['DisplaySetting']
                                            ['Channels']['Channel']['ShortName'])
        except KeyError as e:
            print('Exception:', e)
            try:
                channels.append(metadatadict_czi['ImageDocument']['Metadata']['DisplaySetting']
                                ['Channels']['Channel']['DyeName'])
            except KeyError as e:
                print('Exception:', e)
                channels.append('Dye-CH1')

        # get channel name
        try:
            channels_names.append(metadatadict_czi['ImageDocument']['Metadata']['DisplaySetting']
                                  ['Channels']['Channel']['Name'])
        except KeyError as e:
            print('Exception:', e)
            channels_names.append['CH1']

        # get channel color
        try:
            channels_colors.append(metadatadict_czi['ImageDocument']['Metadata']['DisplaySetting']
                                   ['Channels']['Channel']['Color'])
        except KeyError as e:
            print('Exception:', e)
            channels_colors.append('#80808000')

    # in case of two or more channels
    if metadata['SizeC'] > 1:
        # loop over all channels
        for ch in range(metadata['SizeC']):
            # get name for dyes
            try:
                channels.append(metadatadict_czi['ImageDocument']['Metadata']['DisplaySetting']
                                                ['Channels']['Channel'][ch]['ShortName'])
            except KeyError as e:
                print('Exception:', e)
                try:
                    channels.append(metadatadict_czi['ImageDocument']['Metadata']['DisplaySetting']
                                                    ['Channels']['Channel'][ch]['DyeName'])
                except KeyError as e:
                    print('Exception:', e)
                    channels.append('Dye-CH' + str(ch))

            # get channel names
            try:
                channels_names.append(metadatadict_czi['ImageDocument']['Metadata']['DisplaySetting']
                                      ['Channels']['Channel'][ch]['Name'])
            except KeyError as e:
                print('Exception:', e)
                channels_names.append('CH' + str(ch))

            # get channel colors
            try:
                channels_colors.append(metadatadict_czi['ImageDocument']['Metadata']['DisplaySetting']
                                       ['Channels']['Channel'][ch]['Color'])
            except KeyError as e:
                print('Exception:', e)
                # use grayscale instead
                channels_colors.append('80808000')

    # write channels information (as lists) into metadata dictionary
    metadata['Channels'] = channels
    metadata['ChannelNames'] = channels_names
    metadata['ChannelColors'] = channels_colors

    try:
        metadata['SizeT'] = np.int(metadatadict_czi['ImageDocument']['Metadata']['Information']['Image']['SizeT'])
    except Exception as e:
        # print('Exception:', e)
        if dim2none:
            metadata['SizeT'] = None
        if not dim2none:
            metadata['SizeT'] = 1

    try:
        metadata['SizeM'] = np.int(metadatadict_czi['ImageDocument']['Metadata']['Information']['Image']['SizeM'])
    except Exception as e:
        # print('Exception:', e)
        if dim2none:
            metadata['SizeM'] = None
        if not dim2none:
            metadata['SizeM'] = 1

    try:
        metadata['SizeB'] = np.int(metadatadict_czi['ImageDocument']['Metadata']['Information']['Image']['SizeB'])
    except Exception as e:
        # print('Exception:', e)
        if dim2none:
            metadata['SizeB'] = None
        if not dim2none:
            metadata['SizeB'] = 1

    try:
        metadata['SizeS'] = np.int(metadatadict_czi['ImageDocument']['Metadata']['Information']['Image']['SizeS'])
    except Exception as e:
        # print('Exception:', e)
        if dim2none:
            metadata['SizeS'] = None
        if not dim2none:
            metadata['SizeS'] = 1

    try:
        metadata['SizeH'] = np.int(metadatadict_czi['ImageDocument']['Metadata']['Information']['Image']['SizeH'])
    except Exception as e:
        # print('Exception:', e)
        if dim2none:
            metadata['SizeH'] = None
        if not dim2none:
            metadata['SizeH'] = 1

    try:
        metadata['SizeI'] = np.int(metadatadict_czi['ImageDocument']['Metadata']['Information']['Image']['SizeI'])
    except Exception as e:
        # print('Exception:', e)
        if dim2none:
            metadata['SizeI'] = None
        if not dim2none:
            metadata['SizeI'] = 1

    try:
        metadata['SizeV'] = np.int(metadatadict_czi['ImageDocument']['Metadata']['Information']['Image']['SizeV'])
    except Exception as e:
        # print('Exception:', e)
        if dim2none:
            metadata['SizeV'] = None
        if not dim2none:
            metadata['SizeV'] = 1

    # get the scaling information
    try:
        # metadata['Scaling'] = metadatadict_czi['ImageDocument']['Metadata']['Scaling']
        metadata['XScale'] = float(metadatadict_czi['ImageDocument']['Metadata']['Scaling']['Items']['Distance'][0]['Value']) * 1000000
        metadata['YScale'] = float(metadatadict_czi['ImageDocument']['Metadata']['Scaling']['Items']['Distance'][1]['Value']) * 1000000
        metadata['XScale'] = np.round(metadata['XScale'], 3)
        metadata['YScale'] = np.round(metadata['YScale'], 3)
        try:
            metadata['XScaleUnit'] = metadatadict_czi['ImageDocument']['Metadata']['Scaling']['Items']['Distance'][0]['DefaultUnitFormat']
            metadata['YScaleUnit'] = metadatadict_czi['ImageDocument']['Metadata']['Scaling']['Items']['Distance'][1]['DefaultUnitFormat']
        except KeyError as e:
            print('Key not found:', e)
            metadata['XScaleUnit'] = None
            metadata['YScaleUnit'] = None
        try:
            metadata['ZScale'] = float(metadatadict_czi['ImageDocument']['Metadata']['Scaling']['Items']['Distance'][2]['Value']) * 1000000
            metadata['ZScale'] = np.round(metadata['ZScale'], 3)
            # additional check for faulty z-scaling
            if metadata['ZScale'] == 0.0:
                metadata['ZScale'] = 1.0
            try:
                metadata['ZScaleUnit'] = metadatadict_czi['ImageDocument']['Metadata']['Scaling']['Items']['Distance'][2]['DefaultUnitFormat']
            except KeyError as e:
                print('Key not found:', e)
                metadata['ZScaleUnit'] = metadata['XScaleUnit']
        except Exception as e:
            # print('Exception:', e)
            if dim2none:
                metadata['ZScale'] = None
                metadata['ZScaleUnit'] = None
            if not dim2none:
                # set to isotropic scaling if it was single plane only
                metadata['ZScale'] = metadata['XScale']
                metadata['ZScaleUnit'] = metadata['XScaleUnit']
    except Exception as e:
        print('Exception:', e)
        print('Scaling Data could not be found.')

    # try to get software version
    try:
        metadata['SW-Name'] = metadatadict_czi['ImageDocument']['Metadata']['Information']['Application']['Name']
        metadata['SW-Version'] = metadatadict_czi['ImageDocument']['Metadata']['Information']['Application']['Version']
    except (KeyError, TypeError) as e:
        print(e)
        metadata['SW-Name'] = None
        metadata['SW-Version'] = None

    try:
        metadata['AcqDate'] = metadatadict_czi['ImageDocument']['Metadata']['Information']['Image']['AcquisitionDateAndTime']
    except (KeyError, TypeError) as e:
        print(e)
        metadata['AcqDate'] = None

    # get objective data
    try:
        if isinstance(metadatadict_czi['ImageDocument']['Metadata']['Information']['Instrument']['Objectives']['Objective'], list):
            num_obj = len(metadatadict_czi['ImageDocument']['Metadata']['Information']['Instrument']['Objectives']['Objective'])
        else:
            num_obj = 1
    except (KeyError, TypeError) as e:
        print(e)
        num_obj = 1

    # if there is only one objective found
    if num_obj == 1:
        try:
            metadata['ObjName'].append(metadatadict_czi['ImageDocument']['Metadata']['Information']
                                       ['Instrument']['Objectives']['Objective']['Name'])
        except (KeyError, TypeError) as e:
            print(e)
            metadata['ObjName'].append(None)

        try:
            metadata['ObjImmersion'] = metadatadict_czi['ImageDocument']['Metadata']['Information']['Instrument']['Objectives']['Objective']['Immersion']
        except (KeyError, TypeError) as e:
            print(e)
            metadata['ObjImmersion'] = None

        try:
            metadata['ObjNA'] = np.float(metadatadict_czi['ImageDocument']['Metadata']['Information']
                                         ['Instrument']['Objectives']['Objective']['LensNA'])
        except (KeyError, TypeError) as e:
            print(e)
            metadata['ObjNA'] = None

        try:
            metadata['ObjID'] = metadatadict_czi['ImageDocument']['Metadata']['Information']['Instrument']['Objectives']['Objective']['Id']
        except (KeyError, TypeError) as e:
            print(e)
            metadata['ObjID'] = None

        try:
            metadata['TubelensMag'] = np.float(metadatadict_czi['ImageDocument']['Metadata']['Information']
                                               ['Instrument']['TubeLenses']['TubeLens']['Magnification'])
        except (KeyError, TypeError) as e:
            print(e, 'Using Default Value = 1.0 for Tublens Magnification.')
            metadata['TubelensMag'] = 1.0

        try:
            metadata['ObjNominalMag'] = np.float(metadatadict_czi['ImageDocument']['Metadata']['Information']
                                                 ['Instrument']['Objectives']['Objective']['NominalMagnification'])
        except (KeyError, TypeError) as e:
            print(e, 'Using Default Value = 1.0 for Nominal Magnification.')
            metadata['ObjNominalMag'] = 1.0

        try:
            if metadata['TubelensMag'] is not None:
                metadata['ObjMag'] = metadata['ObjNominalMag'] * metadata['TubelensMag']
            if metadata['TubelensMag'] is None:
                print('No TublensMag found. Use 1 instead')
                metadata['ObjMag'] = metadata['ObjNominalMag'] * 1.0

        except (KeyError, TypeError) as e:
            print(e)
            metadata['ObjMag'] = None

    if num_obj > 1:
        for o in range(num_obj):

            try:
                metadata['ObjName'].append(metadatadict_czi['ImageDocument']['Metadata']['Information']
                                           ['Instrument']['Objectives']['Objective'][o]['Name'])
            except KeyError as e:
                print('Key not found:', e)
                metadata['ObjName'].append(None)

            try:
                metadata['ObjImmersion'].append(metadatadict_czi['ImageDocument']['Metadata']['Information']
                                                ['Instrument']['Objectives']['Objective'][o]['Immersion'])
            except KeyError as e:
                print('Key not found:', e)
                metadata['ObjImmersion'].append(None)

            try:
                metadata['ObjNA'].append(np.float(metadatadict_czi['ImageDocument']['Metadata']['Information']
                                                  ['Instrument']['Objectives']['Objective'][o]['LensNA']))
            except KeyError as e:
                print('Key not found:', e)
                metadata['ObjNA'].append(None)

            try:
                metadata['ObjID'].append(metadatadict_czi['ImageDocument']['Metadata']['Information']
                                         ['Instrument']['Objectives']['Objective'][o]['Id'])
            except KeyError as e:
                print('Key not found:', e)
                metadata['ObjID'].append(None)

            try:
                metadata['TubelensMag'].append(np.float(metadatadict_czi['ImageDocument']['Metadata']['Information']
                                                        ['Instrument']['TubeLenses']['TubeLens'][o]['Magnification']))
            except KeyError as e:
                print('Key not found:', e, 'Using Default Value = 1.0 for Tublens Magnification.')
                metadata['TubelensMag'].append(1.0)

            try:
                metadata['ObjNominalMag'].append(np.float(metadatadict_czi['ImageDocument']['Metadata']['Information']
                                                          ['Instrument']['Objectives']['Objective'][o]['NominalMagnification']))
            except KeyError as e:
                print('Key not found:', e, 'Using Default Value = 1.0 for Nominal Magnification.')
                metadata['ObjNominalMag'].append(1.0)

            try:
                if metadata['TubelensMag'] is not None:
                    metadata['ObjMag'].append(metadata['ObjNominalMag'][o] * metadata['TubelensMag'][o])
                if metadata['TubelensMag'] is None:
                    print('No TublensMag found. Use 1 instead')
                    metadata['ObjMag'].append(metadata['ObjNominalMag'][o] * 1.0)

            except KeyError as e:
                print('Key not found:', e)
                metadata['ObjMag'].append(None)

    # get detector information

    # check if there are any detector entries inside the dictionary
    if pydash.objects.has(metadatadict_czi, ['ImageDocument', 'Metadata', 'Information', 'Instrument', 'Detectors']):

        if isinstance(metadatadict_czi['ImageDocument']['Metadata']['Information']['Instrument']['Detectors']['Detector'], list):
            num_detectors = len(metadatadict_czi['ImageDocument']['Metadata']['Information']['Instrument']['Detectors']['Detector'])
        else:
            num_detectors = 1

        # if there is only one detector found
        if num_detectors == 1:

            # check for detector ID
            try:
                metadata['DetectorID'].append(metadatadict_czi['ImageDocument']['Metadata']['Information']
                                              ['Instrument']['Detectors']['Detector']['Id'])
            except KeyError as e:
                metadata['DetectorID'].append(None)

            # check for detector Name
            try:
                metadata['DetectorName'].append(metadatadict_czi['ImageDocument']['Metadata']['Information']
                                                ['Instrument']['Detectors']['Detector']['Name'])
            except KeyError as e:
                metadata['DetectorName'].append(None)

            # check for detector model
            try:
                metadata['DetectorModel'].append(metadatadict_czi['ImageDocument']['Metadata']['Information']
                                                 ['Instrument']['Detectors']['Detector']['Manufacturer']['Model'])
            except KeyError as e:
                metadata['DetectorModel'].append(None)

            # check for detector type
            try:
                metadata['DetectorType'].append(metadatadict_czi['ImageDocument']['Metadata']['Information']
                                                ['Instrument']['Detectors']['Detector']['Type'])
            except KeyError as e:
                metadata['DetectorType'].append(None)

        if num_detectors > 1:
            for d in range(num_detectors):

                # check for detector ID
                try:
                    metadata['DetectorID'].append(metadatadict_czi['ImageDocument']['Metadata']['Information']
                                                  ['Instrument']['Detectors']['Detector'][d]['Id'])
                except KeyError as e:
                    metadata['DetectorID'].append(None)

                # check for detector Name
                try:
                    metadata['DetectorName'].append(metadatadict_czi['ImageDocument']['Metadata']['Information']
                                                    ['Instrument']['Detectors']['Detector'][d]['Name'])
                except KeyError as e:
                    metadata['DetectorName'].append(None)

                # check for detector model
                try:
                    metadata['DetectorModel'].append(metadatadict_czi['ImageDocument']['Metadata']['Information']
                                                     ['Instrument']['Detectors']['Detector'][d]['Manufacturer']['Model'])
                except KeyError as e:
                    metadata['DetectorModel'].append(None)

                # check for detector type
                try:
                    metadata['DetectorType'].append(metadatadict_czi['ImageDocument']['Metadata']['Information']
                                                    ['Instrument']['Detectors']['Detector'][d]['Type'])
                except KeyError as e:
                    metadata['DetectorType'].append(None)

    # check for well information
    metadata['Well_ArrayNames'] = []
    metadata['Well_Indices'] = []
    metadata['Well_PositionNames'] = []
    metadata['Well_ColId'] = []
    metadata['Well_RowId'] = []
    metadata['WellCounter'] = None
    metadata['SceneStageCenterX'] = []
    metadata['SceneStageCenterY'] = []

    try:
        print('Trying to extract Scene and Well information if existing ...')
        # extract well information from the dictionary
        allscenes = metadatadict_czi['ImageDocument']['Metadata']['Information']['Image']['Dimensions']['S']['Scenes']['Scene']

        # loop over all detected scenes
        for s in range(metadata['SizeS']):

            if metadata['SizeS'] == 1:
                well = allscenes
                try:
                    metadata['Well_ArrayNames'].append(allscenes['ArrayName'])
                except KeyError as e:
                    # print('Key not found in Metadata Dictionary:', e)
                    try:
                        metadata['Well_ArrayNames'].append(well['Name'])
                    except KeyError as e:
                        print('Key not found in Metadata Dictionary:', e, 'Using A1 instead')
                        metadata['Well_ArrayNames'].append('A1')

                try:
                    metadata['Well_Indices'].append(allscenes['Index'])
                except KeyError as e:
                    print('Key not found in Metadata Dictionary:', e)
                    metadata['Well_Indices'].append(1)

                try:
                    metadata['Well_PositionNames'].append(allscenes['Name'])
                except KeyError as e:
                    print('Key not found in Metadata Dictionary:', e)
                    metadata['Well_PositionNames'].append('P1')

                try:
                    metadata['Well_ColId'].append(np.int(allscenes['Shape']['ColumnIndex']))
                except KeyError as e:
                    print('Key not found in Metadata Dictionary:', e)
                    metadata['Well_ColId'].append(0)

                try:
                    metadata['Well_RowId'].append(np.int(allscenes['Shape']['RowIndex']))
                except KeyError as e:
                    print('Key not found in Metadata Dictionary:', e)
                    metadata['Well_RowId'].append(0)

                try:
                    # count the content of the list, e.g. how many time a certain well was detected
                    metadata['WellCounter'] = Counter(metadata['Well_ArrayNames'])
                except KeyError as e:
                    print('Key not found in Metadata Dictionary:', e)
                    metadata['WellCounter'].append(Counter({'A1': 1}))

                try:
                    # get the SceneCenter Position
                    sx = allscenes['CenterPosition'].split(',')[0]
                    sy = allscenes['CenterPosition'].split(',')[1]
                    metadata['SceneStageCenterX'].append(np.double(sx))
                    metadata['SceneStageCenterY'].append(np.double(sy))
                except KeyError as e:
                    metadata['SceneStageCenterX'].append(0.0)
                    metadata['SceneStageCenterY'].append(0.0)

            if metadata['SizeS'] > 1:
                try:
                    well = allscenes[s]
                    metadata['Well_ArrayNames'].append(well['ArrayName'])
                except KeyError as e:
                    # print('Key not found in Metadata Dictionary:', e)
                    try:
                        metadata['Well_ArrayNames'].append(well['Name'])
                    except KeyError as e:
                        print('Key not found in Metadata Dictionary:', e, 'Using A1 instead')
                        metadata['Well_ArrayNames'].append('A1')

                # get the well information
                try:
                    metadata['Well_Indices'].append(well['Index'])
                except KeyError as e:
                    # print('Key not found in Metadata Dictionary:', e)
                    metadata['Well_Indices'].append(None)
                try:
                    metadata['Well_PositionNames'].append(well['Name'])
                except KeyError as e:
                    # print('Key not found in Metadata Dictionary:', e)
                    metadata['Well_PositionNames'].append(None)

                try:
                    metadata['Well_ColId'].append(np.int(well['Shape']['ColumnIndex']))
                except KeyError as e:
                    print('Key not found in Metadata Dictionary:', e)
                    metadata['Well_ColId'].append(None)

                try:
                    metadata['Well_RowId'].append(np.int(well['Shape']['RowIndex']))
                except KeyError as e:
                    print('Key not found in Metadata Dictionary:', e)
                    metadata['Well_RowId'].append(None)

                # count the content of the list, e.g. how many time a certain well was detected
                metadata['WellCounter'] = Counter(metadata['Well_ArrayNames'])

                # try:
                if isinstance(allscenes, list):
                    try:
                        # get the SceneCenter Position
                        sx = allscenes[s]['CenterPosition'].split(',')[0]
                        sy = allscenes[s]['CenterPosition'].split(',')[1]
                        metadata['SceneStageCenterX'].append(np.double(sx))
                        metadata['SceneStageCenterY'].append(np.double(sy))
                    except KeyError as e:
                        print('Key not found in Metadata Dictionary:', e)
                        metadata['SceneCenterX'].append(0.0)
                        metadata['SceneCenterY'].append(0.0)
                if not isinstance(allscenes, list):
                    metadata['SceneStageCenterX'].append(0.0)
                    metadata['SceneStageCenterY'].append(0.0)

            # count the number of different wells
            metadata['NumWells'] = len(metadata['WellCounter'].keys())

    except (KeyError, TypeError) as e:
        print('No valid Scene or Well information found:', e)

    # close CZI file
    czi.close()


    # convert scale unit tom avoid encoding problems
    if convert_scunit:
        if metadata['XScaleUnit'] == 'µm':
            metadata['XScaleUnit'] = 'micron'
        if metadata['YScaleUnit'] == 'µm':
            metadata['YScaleUnit'] = 'micron'
        if metadata['ZScaleUnit'] == 'µm':
            metadata['ZScaleUnit'] = 'micron'

    # imwrite(filename, data, description='micron \xB5'.encode('latin-1')))

    return metadata


def get_additional_metadata_czi(filename):
    """
    Returns a dictionary with additional CZI metadata.

    :param filename: filename of the CZI image
    :type filename: str
    :return: additional_czimd - dictionary with additional CZI metainformation
    :rtype: dict
    """

    # get CZI object and read array
    czi = zis.CziFile(filename)

    # parse the XML into a dictionary
    metadatadict_czi = xmltodict.parse(czi.metadata())
    additional_czimd = {}

    try:
        additional_czimd['Experiment'] = metadatadict_czi['ImageDocument']['Metadata']['Experiment']
    except KeyError as e:
        print('Key not found:', e)
        additional_czimd['Experiment'] = None

    try:
        additional_czimd['HardwareSetting'] = metadatadict_czi['ImageDocument']['Metadata']['HardwareSetting']
    except KeyError as e:
        print('Key not found:', e)
        additional_czimd['HardwareSetting'] = None

    try:
        additional_czimd['CustomAttributes'] = metadatadict_czi['ImageDocument']['Metadata']['CustomAttributes']
    except KeyError as e:
        print('Key not found:', e)
        additional_czimd['CustomAttributes'] = None

    try:
        additional_czimd['DisplaySetting'] = metadatadict_czi['ImageDocument']['Metadata']['DisplaySetting']
    except KeyError as e:
        print('Key not found:', e)
        additional_czimd['DisplaySetting'] = None

    try:
        additional_czimd['Layers'] = metadatadict_czi['ImageDocument']['Metadata']['Layers']
    except KeyError as e:
        print('Key not found:', e)
        additional_czimd['Layers'] = None

    # close CZI file
    czi.close()

    return additional_czimd


def md2dataframe(metadata, paramcol='Parameter', keycol='Value'):
    """Convert the metadata dictionary to a Pandas DataFrame.

    :param metadata: MeteData dictionary
    :type metadata: dict
    :param paramcol: Name of Columns for the MetaData Parameters, defaults to 'Parameter'
    :type paramcol: str, optional
    :param keycol: Name of Columns for the MetaData Values, defaults to 'Value'
    :type keycol: str, optional
    :return: Pandas DataFrame containing all the metadata
    :rtype: Pandas.DataFrame
    """
    mdframe = pd.DataFrame(columns=[paramcol, keycol])

    for k in metadata.keys():
        d = {'Parameter': k, 'Value': metadata[k]}
        df = pd.DataFrame([d], index=[0])
        mdframe = pd.concat([mdframe, df], ignore_index=True)

    return mdframe


def get_dimorder(dimstring):
    """Get the order of dimensions from dimension string

    :param dimstring: string containing the dimensions
    :type dimstring: str
    :return: dims_dict - dictionary with the dimensions and its positions
    :rtype: dict
    :return: dimindex_list - list with indices of dimensions
    :rtype: list
    :return: numvalid_dims - number of valid dimensions
    :rtype: integer
    """

    dimindex_list = []
    dims = ['R', 'I', 'M', 'H', 'V', 'B', 'S', 'T', 'C', 'Z', 'Y', 'X', '0']
    dims_dict = {}

    # loop over all dimensions and find the index
    for d in dims:

        dims_dict[d] = dimstring.find(d)
        dimindex_list.append(dimstring.find(d))

    # check if a dimension really exists
    numvalid_dims = sum(i > 0 for i in dimindex_list)

    return dims_dict, dimindex_list, numvalid_dims


def get_array_czi(filename,
                  replace_value=False,
                  remove_HDim=True,
                  return_addmd=False,
                  forceDim=False,
                  forceDimname='SizeC',
                  forceDimvalue=2):
    """Get the pixel data of the CZI file as multidimensional NumPy.Array

    :param filename: filename of the CZI file
    :type filename: str
    :param replacevalue: replace arrays entries with a specific value with NaN, defaults to False
    :type replacevalue: bool, optional
    :param remove_HDim: remove the H-Dimension (Airy Scan Detectors), defaults to True
    :type remove_HDim: bool, optional
    :param return_addmd: read the additional metadata, defaults to False
    :type return_addmd: bool, optional
    :param forceDim: force a specfic dimension to have a specif value, defaults to False
    :type forceDim: bool, optional
    :param forceDimname: name of the dimension, defaults to 'SizeC'
    :type forceDimname: str, optional
    :param forceDimvalue: value of the dimension, defaults to 2
    :type forceDimvalue: int, optional
    :return: cziarray - dictionary with the dimensions and its positions
    :rtype: NumPy.Array
    :return: metadata - dictionary with CZI metadata
    :rtype: dict
    :return: additional_metadata_czi - dictionary with additional CZI metadata
    :rtype: dict
    """

    metadata = get_metadata_czi(filename,
                                forceDim=forceDim,
                                forceDimname=forceDimname,
                                forceDimvalue=forceDimvalue)

    # get additional metainformation
    additional_metadata_czi = get_additional_metadata_czi(filename)

    # get CZI object and read array
    czi = zis.CziFile(filename)
    cziarray = czi.asarray()

    # check for H dimension and remove
    if remove_HDim and metadata['Axes_czifile'][0] == 'H':
        # metadata['Axes'] = metadata['Axes_czifile'][1:]
        metadata['Axes_czifile'] = metadata['Axes_czifile'].replace('H', '')
        cziarray = np.squeeze(cziarray, axis=0)

    # get additional information about dimension order etc.
    dim_dict, dim_list, numvalid_dims = get_dimorder(metadata['Axes_czifile'])
    metadata['DimOrder CZI'] = dim_dict

    if cziarray.shape[-1] == 3:
        pass
    else:
        # remove the last dimension from the end
        cziarray = np.squeeze(cziarray, axis=len(metadata['Axes_czifile']) - 1)
        metadata['Axes_czifile'] = metadata['Axes_czifile'].replace('0', '')

    if replace_value:
        cziarray = replace_value(cziarray, value=0)

    # close czi file
    czi.close()

    return cziarray, metadata, additional_metadata_czi


def replace_value(data, value=0):
    """Replace specifc values in array with NaN

    :param data: Array where values should be replaced
    :type data: NumPy.Array
    :param value: value inside array to be replaced with NaN, defaults to 0
    :type value: int, optional
    :return: array with new values
    :rtype: NumPy.Array
    """

    data = data.astype('float')
    data[data == value] = np.nan

    return data


def get_scalefactor(metadata):
    """Add scaling factors to the metadata dictionary

    :param metadata: dictionary with CZI or OME-TIFF metadata
    :type metadata: dict
    :return: dictionary with additional keys for scling factors
    :rtype: dict
    """

    # set default scale factor to 1.0
    scalefactors = {'xy': 1.0,
                    'zx': 1.0
                    }

    try:
        # get the factor between XY scaling
        scalefactors['xy'] = np.round(metadata['XScale'] / metadata['YScale'], 3)
        # get the scalefactor between XZ scaling
        scalefactors['zx'] = np.round(metadata['ZScale'] / metadata['YScale'], 3)
    except KeyError as e:
        print('Key not found: ', e, 'Using defaults = 1.0')

    return scalefactors


def calc_scaling(data, corr_min=1.0,
                 offset_min=0,
                 corr_max=0.85,
                 offset_max=0):
    """[summary]

    :param data: Calculate min / max scaling
    :type data: Numpy.Array
    :param corr_min: correction factor for minvalue, defaults to 1.0
    :type corr_min: float, optional
    :param offset_min: offset for min value, defaults to 0
    :type offset_min: int, optional
    :param corr_max: correction factor for max value, defaults to 0.85
    :type corr_max: float, optional
    :param offset_max: offset for max value, defaults to 0
    :type offset_max: int, optional
    :return: list with [minvalue, maxvalue]
    :rtype: list
    """

    # get min-max values for initial scaling
    minvalue = np.round((data.min() + offset_min) * corr_min)
    maxvalue = np.round((data.max() + offset_max) * corr_max)
    print('Scaling: ', minvalue, maxvalue)

    return [minvalue, maxvalue]

def writexml_czi(filename, xmlsuffix='_CZI_MetaData.xml'):
    """Write XML imformation of CZI to disk

    :param filename: CZI image filename
    :type filename: str
    :param xmlsuffix: suffix for the XML file that will be created, defaults to '_CZI_MetaData.xml'
    :type xmlsuffix: str, optional
    :return: filename of the XML file
    :rtype: str
    """

    # open czi file and get the metadata
    czi = zis.CziFile(filename)
    mdczi = czi.metadata()
    czi.close()

    # change file name
    xmlfile = filename.replace('.czi', xmlsuffix)

    # get tree from string
    tree = ET.ElementTree(ET.fromstring(mdczi))

    # write XML file to same folder
    tree.write(xmlfile, encoding='utf-8', method='xml')

    return xmlfile



def getImageSeriesIDforWell(welllist, wellID):
    """
    Returns all ImageSeries (for OME-TIFF) indicies for a specific wellID

    :param welllist: list containing all wellIDs as stringe, e.g. '[B4, B4, B4, B4, B5, B5, B5, B5]'
    :type welllist: list
    :param wellID: string specifying the well, eg.g. 'B4'
    :type wellID: str
    :return: imageseriesindices - list containing all ImageSeries indices, which correspond the the well
    :rtype: list
    """

    imageseries_indices = [i for i, x in enumerate(welllist) if x == wellID]

    return imageseries_indices


def addzeros(number):
    """Convert a number into a string and add leading zeros.
    Typically used to construct filenames with equal lengths.

    :param number: the number
    :type number: int
    :return: zerostring - string with leading zeros
    :rtype: str
    """

    if number < 10:
        zerostring = '0000' + str(number)
    if number >= 10 and number < 100:
        zerostring = '000' + str(number)
    if number >= 100 and number < 1000:
        zerostring = '00' + str(number)
    if number >= 1000 and number < 10000:
        zerostring = '0' + str(number)

    return zerostring


def get_dimpositions(dimstring, tocheck=['B', 'S', 'T', 'Z', 'C']):
    """Simple function to get the indices of the dimension identifiers in a string

    :param dimstring: dimension string
    :type dimstring: str
    :param tocheck: list of entries to check, defaults to ['B', 'S', 'T', 'Z', 'C']
    :type tocheck: list, optional
    :return: dictionary with positions of dimensions inside string
    :rtype: dict
    """
    dimpos = {}
    for p in tocheck:
        dimpos[p] = dimstring.find(p)

    return dimpos


def update5dstack(image5d, image2d,
                  dimstring5d='TCZYX',
                  t=0,
                  z=0,
                  c=0):

    # remove XY
    dimstring5d = dimstring5d.replace('X', '').replace('Y', '')

    if dimstring5d == 'TZC':
        image5d[t, z, c, :, :] = image2d
    if dimstring5d == 'TCZ':
        image5d[t, c, z, :, :] = image2d
    if dimstring5d == 'ZTC':
        image5d[z, t, c, :, :] = image2d
    if dimstring5d == 'ZCT':
        image5d[z, c, t, :, :] = image2d
    if dimstring5d == 'CTZ':
        image5d[c, t, z, :, :] = image2d
    if dimstring5d == 'CZT':
        image5d[c, z, t, :, :] = image2d

    return image5d




def calc_normvar(img2d):
    """Determine normalized focus value for a 2D image
    - based on algorithm F - 11 "Normalized Variance"
    - Taken from: Sun et al., 2004. MICROSCOPY RESEARCH AND TECHNIQUE 65, 139–149.
    - Maximum value is best-focused, decreasing as defocus increases

    :param img2d: 2D image
    :type img2d: NumPy.Array
    :return: normalized focus value for the 2D image
    :rtype: float
    """

    mean = np.mean(img2d)
    height = img2d.shape[0]
    width = img2d.shape[1]

    # subtract the mean and sum up the whole array
    fi = (img2d - mean)**2
    b = np.sum(fi)

    # calculate the normalized variance value
    normvar = b / (height * width * mean)

    return normvar



def find_chan(metadata,channel):
    """Find channel index number based on filter name

    :param metadata: czi metadata
    :type metadata:  dict
    :param: channel: channel name
    :type channel: str
    :rtype: int
    """
    for i, dic in enumerate(metadata['Channels']):
        if dic == channel:
            return i
    return -1
