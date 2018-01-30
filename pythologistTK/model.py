# coding: utf8
from tkinter import *
from tkinter import ttk
from ttkthemes import ThemedStyle
from tkinter.filedialog import *
from pythologistTK import application
from PIL import Image, ImageTk
from openslide import OpenSlide
import pickle
import numpy
from skimage.draw import polygon, polygon_perimeter


class Model:
    def __init__(self, master):

        # master is the tkinter main application
        self.master = master


################################################################################
        # Menu creation
################################################################################
        # Menu bar
        self.menubar = Menu(self.master)

        # File Menu
        self.file_menu = Menu(self.menubar)
        self.file_menu.add_command(label="Open Image",
                                   command=self.open_files)
        self.menubar.add_cascade(label="File", menu=self.file_menu)

        # link the menu to the app
        self.master.config(menu=self.menubar)


################################################################################
        # processable objects
################################################################################
        self.slide = None
        self.image_x_abs = 0.
        self.image_y_abs = 0.
        self.annotations = None


################################################################################
        # View : sub-application (TabApplication)
################################################################################
        # master of the view application is the main tkinter application,
        # not the model itself
        self.view = application.TabApplication(self.master, self)


################################################################################
        # functions for image streaming
################################################################################

    def open_files(self):
        # get path of the slide
        self.slidefilepath = askopenfilename(title="open image",
                                             filetypes=[('mrxs files', '.mrxs'),
                                                        ('all files', '.*')])

        # create the slide object
        self.slide = OpenSlide(self.slidefilepath)
        print("open file : ", self.slidefilepath)
        # get path of the annotation file
        self.annotationfilepath = self.slidefilepath[0:-len(".mrxs")] + ".annot"
        # create the annotation object
        self.annotations = None
        if os.path.exists(self.annotationfilepath):
            self.view.annotapp.isannotation = True
            with open(self.annotationfilepath, "rb") as f:
                self.annotations = pickle.load(f)
            self.view.annotapp.initAnnot()
        else:
            self.annotations = dict()
        self.view.viewapp.initView()

    def initImage(self):
        # define current level of observation to lowest level (highest on pyramid)
        canvasheight = self.view.viewapp.canvas.height
        canvaswidth = self.view.viewapp.canvas.width
        self.level = self.slide.level_count - 1
        print("number of pyramidal levels : ", self.level)

        # create an image low resolution to find ROI in current level
        im = numpy.asarray(self.slide.read_region(location=(0, 0),
                                                  level=self.level,
                                                  size=self.slide.level_dimensions[self.level]))

        # find ROI in current level
        [i, j] = numpy.where(im[:, :, 0] > 0)

        # center of ROI in current level
        ci = round(numpy.mean(i))
        cj = round(numpy.mean(j))
        ci = int(ci)
        cj = int(cj)

        # image position in current level
        ci -= int(canvasheight + (canvasheight / 2))
        cj -= int(canvaswidth + (canvaswidth / 2))

        # image absolute position in slide
        self.image_y_abs = ci * numpy.power(2, self.level)
        self.image_x_abs = cj * numpy.power(2, self.level)

        # image creation
        image = self.slide.read_region(location=(self.image_x_abs,
                                                 self.image_y_abs),
                                       level=self.level,
                                       size=(3 * canvaswidth,
                                             3 * canvasheight))
        return image

    def translateImage(self, xref, yref, event):
        canvasheight = self.view.viewapp.canvas.height
        canvaswidth = self.view.viewapp.canvas.width
        self.image_x_abs -= (event.x - xref) * numpy.power(2, self.level)
        self.image_y_abs -= (event.y - yref) * numpy.power(2, self.level)
        # have to redefine image to store "du rab" for incoming translations
        image = self.slide.read_region(location=(self.image_x_abs,
                                                 self.image_y_abs),
                                       level=self.level,
                                       size=(3 * canvaswidth,
                                             3 * canvasheight))
        return image

    def zoomImage(self, x, y):
        canvasheight = self.view.viewapp.canvas.height
        canvaswidth = self.view.viewapp.canvas.width
        self.image_x_abs = x - int(canvaswidth + (canvaswidth / 2)) * numpy.power(2, self.level)
        self.image_y_abs = y - int(canvasheight + (canvasheight / 2)) * numpy.power(2, self.level)

        # get image position in canvas at new level
        image = self.slide.read_region(location=(self.image_x_abs,
                                                 self.image_y_abs),
                                       level=self.level,
                                       size=(3 * canvaswidth,
                                             3 * canvasheight))
        return image

    def abscenter(self):
        canvasheight = self.view.viewapp.canvas.height
        canvaswidth = self.view.viewapp.canvas.width
        abscenterx = self.image_x_abs + int(canvaswidth + (canvaswidth / 2)) * numpy.power(2, self.level)
        abscentery = self.image_y_abs + int(canvasheight + (canvasheight / 2)) * numpy.power(2, self.level)
        return abscenterx, abscentery

    def zoomIn(self):
        # get absolute center
        absx, absy = self.abscenter()
        # reset level
        if self.level > 0:
            self.level -= 1
        # recompute image
        image = self.zoomImage(absx, absy)
        return image

    def zoomOut(self):
        # get absolute center
        absx, absy = self.abscenter()
        # reset level
        if self.level < self.slide.level_count - 1:
            self.level += 1
        # recompute image
        image = self.zoomImage(absx, absy)
        return image


################################################################################
        # functions for annotations processing
################################################################################
    def annotationNames(self):
        namesNcolors = []
        for key in self.annotations.keys():
            namesNcolors.append({"name": key, "color": self.annotations[key]["color"]})
        return namesNcolors

    def detailedAnnotation(self, name):
        detail = []
        for key in self.annotations[name]:
            detail.append(str(key) + " : " + str(self.annotations[name][key]))
        return detail

    def imageAnnotation(self, name):
        coords = self.annotations[name]["coords"]
        sizex = self.view.annotapp.patchView.width
        sizey = self.view.annotapp.patchView.height
        i = numpy.array([c[1] for c in coords])
        j = numpy.array([c[0] for c in coords])
        imin = i.min()
        jmin = j.min()
        imax = i.max()
        jmax = j.max()
        imiddle = int(float(imax - imin) / 2)
        jmiddle = int(float(jmax - jmin) / 2)
        di = imax - imin
        dj = jmax - jmin
        k = 2
        while (float(di) / numpy.power(2, k)) > sizey and (float(dj) / numpy.power(2, k)) > sizex:
            k += 1
        absoriginx = jmin + int(float(dj) / 2) - (int(float(sizex) / 2) * (2 ** k))
        absoriginy = imin + int(float(di) / 2) - (int(float(sizey) / 2) * (2 ** k))
        image = self.slide.read_region(location=(absoriginx, absoriginy),
                                       level=k,
                                       size=(sizex, sizey))
        bbx = (int(float(sizex) / 2 - ((float(dj) / 2) / (2 ** k))),
               int(float(sizey) / 2 - ((float(di) / 2) / (2 ** k))),
               int(float(sizex) / 2 - ((float(dj) / 2) / (2 ** k)) + (dj / (2 ** k))),
               int(float(sizey) / 2 - ((float(di) / 2) / (2 ** k)) + (di / (2 ** k))))
        return bbx, image
