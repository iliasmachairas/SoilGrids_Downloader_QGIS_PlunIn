# -*- coding: utf-8 -*-
"""
/***************************************************************************
 Soil_Grids_Downloader
                                 A QGIS plugin
 This plug-in is used to download soil properties data from soil grids
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2024-10-05
        git sha              : $Format:%H$
        copyright            : (C) 2024 by Ilias Machairas
        email                : iliasmachairas@outlook.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, Qt
from qgis.PyQt.QtGui import QIcon, QClipboard
from qgis.PyQt.QtWidgets import QAction, QFileDialog
from qgis.core import QgsProject, Qgis, QgsVectorLayer, QgsWkbTypes, QgsMessageLog, QgsMapLayerProxyModel, QgsCoordinateReferenceSystem
from qgis.core import QgsMapLayerType, QgsVectorFileWriter, QgsField
from qgis.PyQt.QtCore import QVariant
from qgis.gui import QgsMapToolEmitPoint, QgsMapToolPan
from urllib.parse import urlencode
import webbrowser
from .SoilPropertyFetcher import SoilPropertyFetcher

# Initialize Qt resources from file resources.py
from .resources import *
# Import the code for the dialog
from .Soil_Grids_Downloader_dialog import Soil_Grids_DownloaderDialog
import os.path
import time
import requests

class Soil_Grids_Downloader:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'Soil_Grids_Downloader_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&Soil Grids Downloader')

        # Check if plugin was started the first time in current QGIS session
        # Must be set in initGui() to survive plugin reloads
        self.first_start = None

        self.dlg = Soil_Grids_DownloaderDialog()
        self.dlg.pushButton_help.clicked.connect(self.open_help_page)
        #self.dlg.pushButton_help.clicked.disconnect()  # This prevents duplicates if already connected.
        #self.dlg.pushButton_help.clicked.connect(self.open_help_page)

        # self.dlg.checkBox_tab2_sand.setChecked(True)  # Sand is selected by default
        # self.dlg.checkBox_tab2_soc.setChecked(True)   # SOC is selected by default

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('Soil_Grids_Downloader', message)


    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            # Adds plugin icon to Plugins toolbar
            self.iface.addToolBarIcon(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""
        #con_path = ':/plugins/Soil_Grids_Downloader/icon.png'
        icon_path = ':/plugins/Soil_Grids_Downloader/plant_2.png'
        self.add_action(
            # icon_path,
            f'{self.plugin_dir}/plant_2.png',
            text=self.tr(u'Download soil properties data'),
            callback=self.run,
            parent=self.iface.mainWindow())

        # will be set False in run()
        self.first_start = True


    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&Soil Grids Downloader'),
                action)
            self.iface.removeToolBarIcon(action)

    def select_output_file(self):
        filename, _filter = QFileDialog.getSaveFileName(
            self.dlg, "Select output filename and destination", "layer_info", '*.shp')
        self.dlg.mLineEdit.setText(filename)

    def open_folder(self):
        # Expand the APPDATA environment variable
        appdata_path = os.path.expandvars(r'%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\soil_grids_downloader\test_point_shp')

        # Open File Explorer at the specified path
        if os.path.exists(appdata_path):
            os.startfile(appdata_path)  # This opens the folder in File Explorer
        else:
            print("The specified directory does not exist.")

    def load_shapefile(self, filepath):
        # Load the new shapefile
        layer_name = os.path.splitext(os.path.basename(filepath))[0]
        layer = QgsVectorLayer(filepath, layer_name, "ogr")

        # Check if the layer was loaded successfully
        if not layer.isValid():
            print(f"Failed to load the shapefile: {filepath}")
            QgsMessageLog.logMessage(f"Failed to load the shapefile: {filepath}", 'MyPlugin')
        else:

            # Add the layer to the current QGIS project
            QgsProject.instance().addMapLayer(layer)
            print(f"Shapefile {filepath} loaded successfully.")

    # Click on the map
    def setup_point_tool(self):
        # Minimize the dialog window
        self.dlg.setWindowState(Qt.WindowMinimized)
        canvas = self.iface.mapCanvas()
        self.pointTool = QgsMapToolEmitPoint(canvas)
        self.pointTool.canvasClicked.connect(self.handle_canvas_click)
        canvas.setMapTool(self.pointTool)

    def handle_canvas_click(self, pointTool):
        # Check the CRS
        current_crs = QgsProject.instance().crs()
        target_crs = QgsCoordinateReferenceSystem("EPSG:4326")  # Example target CRS (WGS 84)

        if current_crs != target_crs:
            self.iface.messageBar().pushMessage("Error", "CRS mismatch! Coordinates not updated.", level=Qgis.Critical)
            QgsMessageLog.logMessage('My message', 'CRS was checked')
        else:
            # Extract coordinates
            x, y = pointTool.x(), pointTool.y()
            QgsMessageLog.logMessage(f"x: {x}", 'MyPlugin')
            QgsMessageLog.logMessage(f"y: {y}", 'MyPlugin')

            # Update the mLineEdit fields - coordinates
            self.dlg.mLineEdit_2.setText(f"{x:.4f}")
            self.dlg.mLineEdit_3.setText(f"{y:.4f}")

            # Update soil properties
            clicked_properties = ['clay', 'sand', 'silt', 'soc', 'nitrogen']

            try:

                clicked_point = SoilPropertyFetcher(lat=y, lon=x)
                property_values = clicked_point.fetch_properties(clicked_properties)
                QgsMessageLog.logMessage(f"clay: {property_values['clay']}", 'MyPlugin')
                if any(value is None for value in property_values.values()):
                    self.iface.messageBar().pushMessage(
                        "Warning",
                        "You either selected an urban area or sea - be careful.",
                        level=Qgis.Warning
                    )
                    QgsMessageLog.logMessage("None values detected in soil properties.", 'MyPlugin')

                self.dlg.mLineEdit_clay.setText(f"{property_values['clay']:.2f}")
                self.dlg.mLineEdit_sand.setText(f"{property_values['sand']:.2f}")
                self.dlg.mLineEdit_silt.setText(f"{property_values['silt']:.2f}")
                self.dlg.mLineEdit_soc.setText(f"{property_values['soc']:.2f}")
                self.dlg.mLineEdit_nitrogen.setText(f"{property_values['nitrogen']:.2f}")

            except Exception as e:
                print(f"Failed to fetch data for point ({x}, {y}): {e}")
                QgsMessageLog.logMessage('Error occurred in Soil Grids API', 'MyPlugin')


        # Restore the dialog window
        self.dlg.setWindowState(Qt.WindowNoState)
        self.dlg.raise_()  # Bring to the foreground
        self.dlg.activateWindow()  # Make it the active window

        # Reset the tool back to pan mode
        pan_tool = QgsMapToolPan(self.iface.mapCanvas())
        self.iface.mapCanvas().setMapTool(pan_tool)

    def copy_to_clipboard(self):
        x_value = self.dlg.mLineEdit_2.text()
        y_value = self.dlg.mLineEdit_3.text()

        clay = self.dlg.mLineEdit_clay.text()
        sand = self.dlg.mLineEdit_sand.text()
        silt = self.dlg.mLineEdit_silt.text()
        soc = self.dlg.mLineEdit_soc.text()
        nitrogen = self.dlg.mLineEdit_nitrogen.text()

        # Format the clipboard content
        clipboard_content = (
            f"X: {x_value}\n"
            f"Y: {y_value}\n"
            f"Clay: {clay}\n"
            f"Sand: {sand}\n"
            f"Silt: {silt}\n"
            f"SOC: {soc}\n"
            f"Nitrogen: {nitrogen}"
        )

        clipboard = QCoreApplication.instance().clipboard()
        clipboard.setText(clipboard_content)

        self.iface.messageBar().pushMessage(
            "Data Copied",
            "All parameters copied to clipboard.",
            level=Qgis.Info,
            duration=3
        )

        # push_copy_Button

    def toggle_copy_button(self):
        x_value = self.dlg.mLineEdit_2.text()
        y_value = self.dlg.mLineEdit_3.text()

        # Enable button only if both fields have text
        if x_value and y_value:
            self.dlg.push_copy_Button.setEnabled(True)
        else:
            self.dlg.push_copy_Button.setEnabled(False)

    def open_help_page(self):
        # Opens a help web page
        webbrowser.open("https://link.springer.com/journal/11067")

    def close_window(self):
        """Closes the dialog window when the button is clicked."""
        self.dlg.close()


    def run(self):
        """Run method that performs all the real work"""

        # Create the dialog with elements (after translation) and keep reference
        # Only create GUI ONCE in callback, so that it will only load when the plugin is started
        if self.first_start == True:
            self.first_start = False
            # self.dlg = Soil_Grids_DownloaderDialog()
            self.dlg.toolButton.clicked.connect(self.select_output_file)

        # Fetch the currently loaded layers
        # layers = QgsProject.instance().layerTreeRoot().children()
        # Clear the contents of the comboBox from previous runs

        QgsMessageLog.logMessage('My message', 'MyPlugin')

        # Get the root layer tree
        # self.root = QgsProject.instance().layerTreeRoot()
        # # Initialize an empty list to store the matching layers
        # self.point_layers_epsg_4326 = []
        #
        # # Iterate through the children (layers)
        # for layer_tree_layer in self.root.children():
        #     layer = layer_tree_layer.layer()
        #     print(layer)
        #     if isinstance(layer, QgsVectorLayer):  # Check if it's a vector layer
        #         if layer.geometryType() == QgsWkbTypes.PointGeometry:  # Check if it's a point vector
        #             # Check if the layer's CRS is EPSG:4326
        #             if layer.crs().authid() == 'EPSG:4326':
        #                 self.point_layers_epsg_4326.append(layer)
        #                 #self.dlg.mMapLayerComboBox.addLayer(layer)

        # Filtering the combo-box
        self.map_layers = QgsProject.instance().mapLayers().values()
        self.allow_list = [
            lyr.id() for lyr in self.map_layers if lyr.type() == QgsMapLayerType.VectorLayer
                                                   and lyr.geometryType() == QgsWkbTypes.PointGeometry
                                                   and lyr.crs().authid() == 'EPSG:4326'
        ]
        self.except_list = [l for l in self.map_layers if l.id() not in self.allow_list]
        self.dlg.mMapLayerComboBox.setExceptedLayerList(self.except_list)

        # Expand the APPDATA environment variable
        self.dlg.pushButton.clicked.connect(self.open_folder)

        # click on the map
        self.dlg.pushButton_2.clicked.connect(self.setup_point_tool)

        # self.dlg.mMapLayerComboBox.clear()
        # .dlg.mMapLayerComboBox
        # self.dlg.mMapLayerComboBox.setFilters(QgsMapLayerProxyModel.PointLayer)
        # selectedlayer = self.dlg.mMapLayerComboBox.currentLayer()
        # selectedlayername = selectedlayer.name()
        # QgsMessageLog.logMessage(selectedlayername, 'MyPlugin')

        ## Copy button
        self.dlg.push_copy_Button.clicked.connect(self.copy_to_clipboard)
        self.dlg.mLineEdit_2.textChanged.connect(self.toggle_copy_button)
        self.dlg.mLineEdit_3.textChanged.connect(self.toggle_copy_button)
        # Initially disable the button
        self.dlg.push_copy_Button.setEnabled(False)

        # Help page and Close Page
        self.dlg.pushButton_close.clicked.connect(self.close_window)

        # show the dialog
        self.dlg.show()
        # Run the dialog event loop
        result = self.dlg.exec_()
        # See if OK was pressed
        if result:
            output_filename = self.dlg.mLineEdit.text()

            # Check if filename is empty
            if not output_filename:
                self.iface.messageBar().pushMessage(
                    "Error", "Please select a valid output filename.",
                    level=Qgis.Critical, duration=5)
                return  # Exit if no filename is provided

            selectedlayer = self.dlg.mMapLayerComboBox.currentLayer()
            selectedlayername = selectedlayer.name()
            input_filepath = selectedlayer.dataProvider().dataSourceUri()


            QgsMessageLog.logMessage(selectedlayername, 'MyPlugin')
            QgsMessageLog.logMessage(input_filepath, 'MyPlugin')

            # todo fix this warning
            # Step 1: Write the input shapefile to a new output shapefil5e first (without modifications)
            writer = QgsVectorFileWriter(output_filename, "UTF-8", selectedlayer.fields(), QgsWkbTypes.Point,
                                         selectedlayer.crs(), "ESRI Shapefile")


            for feature in selectedlayer.getFeatures():
                print(feature)
                writer.addFeature(feature)

            del writer  # Close the writer to finish writing the new shapefile
            QgsMessageLog.logMessage("Shapefile copied", 'MyPlugin')

            # Step 2: Reopen the output shapefile and add a new field for the soil property
            output_layer = QgsVectorLayer(output_filename, "output_layer", "ogr")

            if not output_layer.isValid():
                raise Exception(f"Failed to load the output shapefile: {output_filename}")

            # properties = ['clay', 'sand', 'silt', 'soc', 'nitrogen']
            properties = self.dlg.get_selected_properties()
            if not properties:
                self.iface.messageBar().pushMessage(
                    "Error", "Please select at least one property.",
                    level=Qgis.Critical, duration=5)
                return  # Exit if no properties are selected

            # new_column_name = "Clay"
            for property_name in properties:
                output_layer.dataProvider().addAttributes([QgsField(property_name, QVariant.Double, "double", 10, 2)])
            output_layer.updateFields()

            output_layer.startEditing()  # Start an editing session

            for feature in output_layer.getFeatures():
                geom = feature.geometry()
                lat, lon = geom.asPoint().y(), geom.asPoint().x()  # Get latitude and longitude
                QgsMessageLog.logMessage(f"Latitude: {lat}, Longitude: {lon}", 'MyPlugin', Qgis.Info)
                # QgsMessageLog.logMessage(str(lat), str(lon), 'MyPlugin')

                # Fetch soil property
                fetcher = SoilPropertyFetcher(lat, lon)
                # QgsMessageLog.logMessage(fetcher, 'MyPlugin')
                try:
                    property_values = fetcher.fetch_properties(properties)
                    # QgsMessageLog.logMessage(property_values, 'MyPlugin')
                    for property_name, value in property_values.items():
                        feature.setAttribute(feature.fieldNameIndex(property_name), value)

                except Exception as e:
                    print(f"Failed to fetch data for point ({lat}, {lon}): {e}")
                    QgsMessageLog.logMessage('Error occurred', 'MyPlugin')
                    feature.setAttribute(feature.fieldNameIndex(property_name), None)  # Set None if fetching fails

                output_layer.updateFeature(feature)  # Update the feature in the layer

            output_layer.commitChanges()  # Commit the changes to save the edits

            # Shapefile Loading
            if self.dlg.checkBox_load_shp.isChecked():
                self.load_shapefile(output_filename)


            print(f"New shapefile updated with soil properties: {output_layer}")