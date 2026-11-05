"""Object editing controller, isolated from the legacy brush workflow."""
from copy import deepcopy
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor, QImage, QPixmap, QIcon
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QHBoxLayout, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QSlider,
                               QVBoxLayout, QWidget, QPushButton, QSpinBox)

from . import layout
from .dialogs import choose_color, text_input
from .i18n import tr
from .materials import MaterialLayer, audit, material_color, image_digest
from .regions import background_mask, pack, paint_mask, region_outline, scene_regions, unpack
from .segmentation import Segmenter


class SelectionJob(QThread):
    completed=Signal(int,object)
    failed=Signal(int,str)

    def __init__(self,serial,segmenter,image,points,box,device,backend):
        super().__init__()
        self.serial=serial
        self.args=segmenter,image.copy(),deepcopy(points),deepcopy(box),device,backend

    def run(self):
        try:
            segmenter,image,points,box,device,backend=self.args
            result=(segmenter.propose(image,device,self.isInterruptionRequested,'large' if backend=='proposals-large' else 'small') if backend.startswith('proposals') else
                    segmenter.predict(image,points,box,device,backend,self.isInterruptionRequested))
            if not self.isInterruptionRequested():
                self.completed.emit(self.serial,result)
        except Exception as error:
            self.failed.emit(self.serial,str(error))


class ObjectEditor:
    def build_objects(self):
        self.segmenter=Segmenter()
        self.selection_job=None
        self.selection_serial=0
        self.selection_points=[]
        self.selection_mask=None
        self.selection_candidates=[]
        self.selection_uid=None
        self.selection_box=None
        self.selection_add=None
        self.selection_remove=None
        self.selection_source='manual'
        self.selection_history=[]
        self.selection_redo=[]
        self.object_syncing=False
        self.canvas.selected_point.connect(self.object_point)
        self.object_tab=self.tabs.count()
        pane=layout.tab(self.tabs,tr('Объекты'))
        pane.addWidget(layout.label(tr('Выберите предмет, уточните границы и задайте цвет.')))
        self.object_list=QListWidget()
        self.object_list.setFixedHeight(60)
        self.object_list.currentRowChanged.connect(self.select_object)
        pane.addWidget(self.object_list)
        layout.row(pane,layout.button(tr('Новый объект'),self.new_object),layout.button(tr('Убрать'),self.delete_object))
        self.object_name=QLineEdit();self.object_name.setPlaceholderText(tr('Название объекта'))
        pane.addWidget(self.object_name)
        self.object_backend=QComboBox()
        self.object_backend.addItem('SAM 2.1 Small','sam2')
        self.object_backend.addItem('SAM 2.1 Large','sam2-large')
        self.object_backend.addItem(tr('По контурам'),'contour')
        default_backend='sam2-large' if Segmenter.available('large') else 'sam2' if Segmenter.available() else 'contour'
        saved_backend=self.config.value('selection_backend',default_backend)
        index=self.object_backend.findData(saved_backend)
        self.object_backend.setCurrentIndex(max(0,index))
        self.object_backend.currentIndexChanged.connect(self.selection_backend_changed)
        self.object_tool=QComboBox()
        for name,key in ((tr('Выбрать предмет'),'object'),(tr('Добавить участок'),'region_add'),
                         (tr('Исключить участок'),'region_remove'),(tr('Лассо области'),'region_lasso'),
                         (tr('Ограничить кадром'),'region_box'),(tr('Перемещение'),'view')):
            self.object_tool.addItem(name,key)
        self.object_tool.currentIndexChanged.connect(self.change_tool)
        pane.addWidget(self.object_tool)
        self.object_parts=QCheckBox(tr('Раздельные части'))
        pane.addWidget(self.object_parts)
        self.object_parts.toggled.connect(self.selection_mode_changed)
        layout.row(pane,layout.button(tr('Отменить'),self.undo),layout.button(tr('Вернуть'),self.redo))
        self.object_tip=layout.label(tr('Нажмите на предмет. Shift или правая кнопка исключают лишнее.'))
        pane.addWidget(self.object_tip)
        self.candidate=QComboBox();self.candidate.currentIndexChanged.connect(self.choose_candidate)
        pane.addWidget(self.candidate)
        self.region_scope=QComboBox();self.region_scope.addItem(tr('Вся страница'),None)
        self.region_scope.currentIndexChanged.connect(self.choose_scope)
        self.show_region=QCheckBox(tr('Показать область'));self.show_region.toggled.connect(self.update_object_overlay)
        pane.addWidget(self.show_region)
        self.object_color=layout.button(tr('Выбрать цвет'),self.choose_object_color)
        self.object_hex=QLineEdit('#287FE8');self.object_hex.setMaximumWidth(90)
        self.object_hex.editingFinished.connect(self.object_hex_changed)
        color_row=QHBoxLayout();color_row.addWidget(self.object_color);color_row.addWidget(self.object_hex)
        pane.insertLayout(1,color_row)
        self.material_preview=QLabel();pane.insertWidget(2,self.material_preview)
        self.object_apply=layout.button(tr('Применить цвет'),self.apply_object,'primary')
        self.right.layout().insertWidget(2,self.object_apply)
        self.object_apply.hide()
        size=QSpinBox();size.setRange(1,512);size.setValue(self.diameter.value())
        size.setSuffix(tr(' пикс.'));size.valueChanged.connect(self.diameter.setValue)
        self.diameter.valueChanged.connect(size.setValue)
        layout.row(pane,layout.label(tr('Диаметр кисти')),size)
        layout.row(pane,layout.button(tr('Заблокировать'),self.lock_object),layout.button(tr('Защитить фон'),self.protect_background))
        details=QWidget();advanced=QVBoxLayout(details);advanced.setContentsMargins(0,0,0,0)
        toggle=QPushButton(tr('Настройки'));toggle.setCheckable(True);toggle.toggled.connect(details.setVisible)
        pane.addWidget(toggle);pane.addWidget(details);details.hide()
        self.material_name=QLineEdit();self.material_name.setPlaceholderText(tr('Материал палитры'))
        self.character_name=QLineEdit();self.character_name.setPlaceholderText(tr('Персонаж'))
        advanced.addWidget(self.character_name);advanced.addWidget(self.material_name)
        self.material_saturation=self.object_slider(advanced,tr('Насыщенность'),0,150,100)
        self.material_light=self.object_slider(advanced,tr('Светлота'),-30,30,0)
        self.material_dark=self.object_slider(advanced,tr('Осветлить чёрный материал'),0,60,0)
        for slider in (self.material_saturation,self.material_light,self.material_dark):
            slider.valueChanged.connect(self.preview_material)
        self.object_hex.textChanged.connect(self.preview_material)
        self.preview_material()
        advanced.addWidget(self.object_backend);advanced.addWidget(self.region_scope)
        advanced.addWidget(layout.button(tr('Найти кадры'),self.find_frames))
        advanced.addWidget(layout.button(tr('Предложить объекты'),self.propose_objects))
        advanced.addWidget(layout.button(tr('Скрыть / показать'),self.toggle_object))
        advanced.addWidget(layout.button(tr('Вернуть оригинал'),self.protect_original_region))
        advanced.addWidget(layout.button(tr('Цвет из референса'),self.reference_color))
        advanced.addWidget(layout.button(tr('Связать палитру'),self.link_material))
        advanced.addWidget(layout.button(tr('Применить к связанным'),self.apply_linked))
        advanced.addWidget(layout.button(tr('Проверить качество'),self.quality_report))
        self.object_state=layout.label('');pane.addWidget(self.object_state)
        pane.addStretch()
        self.set_color_btn.setText(tr('Перекрасить объект'))
        self.set_color_btn.clicked.disconnect()
        self.set_color_btn.clicked.connect(self.open_objects)
        self.candidate.hide()

    def preview_material(self,*args):
        color=QColor(self.object_hex.text())
        if not color.isValid() or not hasattr(self,'material_dark'):return
        chip=QPixmap(18,18);chip.fill(color);self.object_color.setIcon(QIcon(chip))
        ramp=np.tile(np.linspace(0,255,220,dtype=np.uint8),(24,1))
        rgb=material_color(ramp,color.getRgb()[:3],self.material_saturation.value()/100,
                           self.material_light.value()/100,self.material_dark.value()/100)
        image=QImage(rgb.data,220,24,220*3,QImage.Format_RGB888).copy()
        self.material_preview.setPixmap(QPixmap.fromImage(image))

    def object_slider(self,pane,name,lo,hi,value):
        title=QLabel(f'{name} · {value}')
        pane.addWidget(title)
        control=QSlider(Qt.Horizontal);control.setRange(lo,hi);control.setValue(value)
        control.valueChanged.connect(lambda v:title.setText(f'{name} · {v}'))
        pane.addWidget(control)
        return control

    def open_objects(self):
        self.ai_manual.setChecked(True)
        self.right.show();self.tabs.setCurrentIndex(self.object_tab)
        self.object_tool.setCurrentIndex(0)
        self.change_tool()

    def reset_object_selection(self):
        self.selection_serial+=1
        if self.selection_job:
            self.selection_job.requestInterruption()
        self.selection_points=[];self.selection_mask=None;self.selection_candidates=[]
        self.selection_history=[];self.selection_redo=[]
        self.selection_uid=None;self.selection_box=None
        self.selection_add=None;self.selection_remove=None
        self.canvas.object_overlay=QPixmap();self.canvas.object_points=[]
        if hasattr(self,'candidate'):
            self.candidate.clear()
            self.candidate.hide()

    def refresh_objects(self):
        if not hasattr(self,'object_list'):
            return
        p=self.current()
        selected=self.selection_uid
        self.object_syncing=True
        self.object_list.clear()
        for layer in p.layers if p else []:
            prefix='[L] ' if layer.locked else '' if layer.visible else '[ ] '
            item=QListWidgetItem(prefix+layer.name)
            item.setData(Qt.UserRole,layer.uid)
            self.object_list.addItem(item)
            if layer.uid==selected:self.object_list.setCurrentItem(item)
        self.region_scope.clear();self.region_scope.addItem(tr('Вся страница'),None)
        for i,box in enumerate(p.regions if p else [],1):
            self.region_scope.addItem(tr('Кадр {0}',i),box)
            if box==self.selection_box:self.region_scope.setCurrentIndex(i)
        self.object_syncing=False
        enabled=bool(p and self.original is not None and not self.worker and not self.selection_job)
        self.object_apply.setEnabled(enabled and self.selection_mask is not None)
        self.object_list.setEnabled(enabled)

    def selected_layer(self):
        p=self.current()
        return next((layer for layer in p.layers if layer.uid==self.selection_uid),None) if p else None

    def new_object(self):
        if not self.current() or self.worker:return
        self.reset_object_selection()
        self.object_name.setText(tr('Объект {0}',len(self.current().layers)+1))
        self.material_name.clear();self.character_name.clear()
        self.material_saturation.setValue(100);self.material_light.setValue(0);self.material_dark.setValue(0)
        self.object_parts.setChecked(False)
        self.object_list.clearSelection()
        self.open_objects();self.refresh_objects();self.canvas.update()

    def select_object(self,index):
        if self.object_syncing or index<0:return
        p=self.current()
        if not p or index>=len(p.layers):return
        layer=p.layers[index]
        self.reset_object_selection()
        self.selection_serial+=1
        self.selection_uid=layer.uid
        if layer.source_digest and layer.source_digest!=image_digest(self.original):
            self.object_state.setText(tr('Исходный файл изменился во время обработки. Повторите страницу.'))
            self.refresh_objects();return
        self.selection_mask=unpack(layer.mask,self.original.size)
        self.selection_points=deepcopy(layer.prompts)
        self.selection_box=layer.scope
        self.selection_source=layer.backend
        self.object_parts.blockSignals(True);self.object_parts.setChecked('-parts' in layer.backend);self.object_parts.blockSignals(False)
        self.selection_add=unpack(layer.manual_add,self.original.size) if layer.manual_add else None
        self.selection_remove=unpack(layer.manual_remove,self.original.size) if layer.manual_remove else None
        self.object_name.setText(layer.name)
        self.object_hex.setText(QColor(*layer.color).name().upper())
        self.material_name.setText(layer.material);self.character_name.setText(layer.character)
        self.material_saturation.setValue(round(layer.saturation*100))
        self.material_light.setValue(round(layer.lightness*100))
        self.material_dark.setValue(round(layer.dark_lift*100))
        self.object_state.setText(tr('Заблокировано') if layer.locked else '')
        self.show_region.setChecked(True)
        self.update_object_overlay();self.refresh_objects()

    def object_point(self,x,y,positive):
        p=self.current()
        if not p or self.worker or self.selection_job:return
        layer=self.selected_layer()
        if layer and layer.locked:
            self.object_state.setText(tr('Заблокировано'));return
        if not positive and not any(point[2] for point in self.selection_points):return
        self.remember_selection()
        self.selection_points.append((x,y,bool(positive)))
        self.show_region.setChecked(True)
        self.selection_serial+=1
        self.run_selection()

    def selection_snapshot(self):
        return (deepcopy(self.selection_points),*(pack(value) if value is not None else None
                 for value in (self.selection_mask,self.selection_add,self.selection_remove)))

    def remember_selection(self):
        self.selection_history.append(self.selection_snapshot())
        self.selection_history=self.selection_history[-20:];self.selection_redo.clear()

    def undo_selection(self,redo=False):
        if self.tabs.currentIndex()!=self.object_tab:return False
        stack=self.selection_redo if redo else self.selection_history
        other=self.selection_history if redo else self.selection_redo
        if not stack:return False
        self.selection_serial+=1
        if self.selection_job:self.selection_job.requestInterruption()
        other.append(self.selection_snapshot())
        self.selection_points,mask,added,removed=stack.pop()
        self.selection_mask,self.selection_add,self.selection_remove=(
            unpack(value,self.original.size) if value else None for value in (mask,added,removed))
        self.selection_candidates=[];self.candidate.clear();self.candidate.hide()
        self.update_object_overlay();self.refresh_objects();return True

    def run_selection(self):
        p=self.current()
        if not p or self.original is None or self.selection_job:return
        backend=self.object_backend.currentData()
        if self.object_parts.isChecked() and backend.startswith('sam2'):backend+='-parts'
        job=SelectionJob(self.selection_serial,self.segmenter,self.original,self.selection_points,
                         self.selection_box,p.settings.device,backend)
        self.selection_job=job
        self.stop_btn.setEnabled(True);self.progress.setRange(0,0)
        self.object_state.setText(tr('Выделение объекта…'))
        job.completed.connect(self.selection_ready)
        job.failed.connect(self.selection_failed)
        job.finished.connect(self.selection_finished)
        self.update_object_overlay();self.refresh();job.start()

    def selection_mode_changed(self):
        layer=self.selected_layer()
        if self.selection_points and not self.selection_job and not self.worker and not (layer and layer.locked):self.run_selection()

    def selection_backend_changed(self):
        self.config.setValue('selection_backend',self.object_backend.currentData())
        self.selection_mode_changed()

    def propose_objects(self):
        if not self.current() or self.original is None or self.worker or self.selection_job:return
        self.new_object()
        backend='proposals-large' if self.object_backend.currentData()=='sam2-large' else 'proposals'
        job=SelectionJob(self.selection_serial,self.segmenter,self.original,[],None,
                         self.current().settings.device,backend)
        self.selection_job=job
        self.stop_btn.setEnabled(True);self.progress.setRange(0,0)
        self.object_state.setText(tr('Выделение объекта…'))
        job.completed.connect(self.selection_ready);job.failed.connect(self.selection_failed)
        job.finished.connect(self.selection_finished)
        self.refresh();job.start()

    def selection_ready(self,serial,payload):
        if serial!=self.selection_serial or self.closing:return
        masks,scores,info=payload
        if not masks:return
        self.selection_candidates=masks;self.selection_source=info.get('engine','manual')
        self.candidate.blockSignals(True);self.candidate.clear()
        for i in range(len(masks)):
            self.candidate.addItem(tr('Вариант {0}',i+1))
        self.candidate.blockSignals(False)
        self.candidate.setVisible(len(masks)>1)
        self.choose_candidate(0)
        self.object_state.setText(tr('Проверьте границы. Добавьте или исключите участки.'))

    def choose_candidate(self,index):
        if 0<=index<len(self.selection_candidates):
            self.selection_mask=self.selection_candidates[index].copy()
            if self.selection_add is not None:self.selection_mask[self.selection_add>0]=255
            if self.selection_remove is not None:self.selection_mask[self.selection_remove>0]=0
            if self.selection_source=='sam2.1-proposals':
                distance=cv2.distanceTransform(np.uint8(self.selection_mask>=128),cv2.DIST_L2,3)
                y,x=np.unravel_index(distance.argmax(),distance.shape)
                self.selection_points=[(x/(distance.shape[1]-1),y/(distance.shape[0]-1),True)]
            self.show_region.setChecked(True)
            self.update_object_overlay();self.refresh_objects()

    def selection_failed(self,serial,message):
        if serial==self.selection_serial:
            self.object_state.setText(message)

    def selection_finished(self):
        job=self.selection_job;self.selection_job=None
        if job:job.deleteLater()
        self.refresh()
        if self.closing:self.close()

    def update_object_overlay(self,*args):
        self.canvas.object_points=self.selection_points
        if not self.show_region.isChecked():
            self.canvas.object_points=[]
            self.canvas.object_overlay=QPixmap();self.canvas.update();return
        if self.selection_mask is None:
            self.canvas.object_overlay=QPixmap();self.canvas.update();return
        mask=self.selection_mask
        outline=region_outline(mask)
        rgba=np.zeros((*mask.shape,4),np.uint8);rgba[:,:,:3]=(102,228,190)
        rgba[:,:,3]=np.maximum(outline,np.uint8(mask.astype(np.float32)*.22) if self.show_region.isChecked() else 0)
        image=QImage(rgba.data,rgba.shape[1],rgba.shape[0],rgba.shape[1]*4,QImage.Format_RGBA8888).copy()
        self.canvas.object_overlay=QPixmap.fromImage(image);self.canvas.update()

    def handle_region_stroke(self,stroke):
        if not stroke.kind.startswith('region_'):return False
        if not self.current() or self.worker or self.selection_job:return True
        if stroke.kind=='region_box':
            pts=np.asarray(stroke.points)
            lo,hi=pts.min(0),pts.max(0)
            if np.min(hi-lo)>.01:
                self.selection_box=[*lo,*hi]
                self.current().regions.append(self.selection_box)
                self.refresh_objects();self.schedule_save()
                if self.selection_points:self.run_selection()
            return True
        layer=self.selected_layer()
        if layer and layer.locked:return True
        self.remember_selection()
        if self.selection_mask is None:
            self.selection_mask=np.zeros((self.original.height,self.original.width),np.uint8)
        if self.selection_add is None:self.selection_add=np.zeros_like(self.selection_mask)
        if self.selection_remove is None:self.selection_remove=np.zeros_like(self.selection_mask)
        add=stroke.kind!='region_remove'
        painted=paint_mask(np.zeros_like(self.selection_mask),stroke.points,stroke.width,True,stroke.kind=='region_lasso')>0
        self.selection_add[painted]=255 if add else 0
        self.selection_remove[painted]=0 if add else 255
        self.selection_mask=paint_mask(self.selection_mask,stroke.points,stroke.width,
                                       stroke.kind!='region_remove',stroke.kind=='region_lasso')
        self.selection_source='manual' if not self.selection_points else self.selection_source+'+manual'
        self.show_region.setChecked(True)
        self.update_object_overlay();self.refresh_objects()
        return True

    def save_layer_history(self):
        p=self.current()
        if p:
            p.layer_history.append([layer.serialize() for layer in p.layers])
            p.layer_history=p.layer_history[-20:];p.layer_redo.clear()

    def apply_object(self):
        p=self.current();layer=self.selected_layer()
        if not p or self.worker or self.selection_job or self.selection_mask is None:return
        if layer and layer.locked:
            self.object_state.setText(tr('Заблокировано'));return
        color=QColor('#'+self.object_hex.text().strip().lstrip('#'))
        if not color.isValid():return
        self.begin_trial(p);self.save_layer_history()
        if not p.version() and not self.has_color(p):p.original_base=True
        if layer is None:
            layer=MaterialLayer(mask=pack(self.selection_mask));p.layers.append(layer)
        layer.mask=pack(self.selection_mask)
        layer.source_digest=image_digest(self.original)
        layer.name=self.object_name.text().strip() or tr('Объект {0}',len(p.layers))
        layer.color=color.getRgb()[:3]
        layer.material=self.material_name.text().strip();layer.character=self.character_name.text().strip()
        layer.saturation=self.material_saturation.value()/100
        layer.lightness=self.material_light.value()/100;layer.dark_lift=self.material_dark.value()/100
        layer.prompts=deepcopy(self.selection_points);layer.scope=self.selection_box;layer.backend=self.selection_source
        layer.manual_add=pack(self.selection_add) if self.selection_add is not None else ''
        layer.manual_remove=pack(self.selection_remove) if self.selection_remove is not None else ''
        self.selection_uid=layer.uid;p.version_name=layer.name
        self.selection_history=[];self.selection_redo=[]
        self.show_region.setChecked(False)
        self.refresh_objects();self.changed();self.persist()
        self.object_state.setText(tr('Проба готова. Сравните и примите или отмените.'))

    def delete_object(self):
        p=self.current();layer=self.selected_layer()
        if p and layer and not self.worker and not layer.locked:
            self.begin_trial(p);self.save_layer_history()
            p.layers.remove(layer);self.reset_object_selection();self.refresh_objects();self.changed()

    def lock_object(self):
        p=self.current();layer=self.selected_layer()
        if not p or not layer or self.worker or self.preview_job or self.preview_timer.isActive():return
        self.begin_trial(p);self.save_layer_history()
        layer.locked=not layer.locked
        if layer.locked:
            picture=self.canvas.result if not self.canvas.result.isNull() else self.canvas.original
            layer.frozen=pack(np.asarray(Image.fromqpixmap(picture).convert('RGB')))
        self.refresh_objects();self.changed()

    def toggle_object(self):
        p=self.current();layer=self.selected_layer()
        if p and layer and not self.worker:
            self.begin_trial(p);self.save_layer_history();layer.visible=not layer.visible
            self.refresh_objects();self.changed()

    def protect_background(self):
        if not self.current() or self.original is None or self.worker:return
        self.new_object()
        self.selection_mask=background_mask(np.asarray(self.original.convert('L')))
        self.object_name.setText(tr('Фон'))
        self.selection_source='border-paper'
        self.show_region.setChecked(True)
        self.update_object_overlay();self.refresh_objects()
        # This is a proposal. The user can remove white clothing before protecting it.
        box=QMessageBox(self);box.setWindowTitle(tr('Защитить фон'))
        box.setText(tr('Проверьте область фона. Защитить её исходными пикселями?'))
        box.addButton(tr('Заблокировать'),QMessageBox.AcceptRole)
        cancel=box.addButton(tr('Отмена'),QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton()==cancel:return
        p=self.current();self.begin_trial(p);self.save_layer_history()
        p.layers.append(MaterialLayer(pack(self.selection_mask),tr('Фон'),locked=True,original=True,backend='border-paper',source_digest=image_digest(self.original)))
        self.selection_uid=p.layers[-1].uid
        if not p.version() and not self.has_color(p):p.original_base=True
        self.refresh_objects();self.changed()

    def protect_original_region(self):
        p=self.current()
        if not p or self.selection_mask is None or self.worker:return
        layer=self.selected_layer()
        self.begin_trial(p);self.save_layer_history()
        if layer is None:
            layer=MaterialLayer(pack(self.selection_mask),self.object_name.text() or tr('Объект {0}',len(p.layers)+1))
            p.layers.append(layer)
        layer.mask=pack(self.selection_mask);layer.locked=True;layer.original=True;layer.frozen=''
        layer.source_digest=image_digest(self.original)
        self.selection_uid=layer.uid
        if not p.version() and not self.has_color(p):p.original_base=True
        self.refresh_objects();self.changed()

    def choose_scope(self,index):
        if self.object_syncing:return
        self.selection_box=self.region_scope.itemData(index)
        if self.selection_points and not self.selection_job:self.run_selection()

    def find_frames(self):
        p=self.current()
        if p and self.original is not None and not self.worker:
            p.regions=scene_regions(np.asarray(self.original.convert('L')))
            self.refresh_objects();self.schedule_save()
            self.object_state.setText(tr('Кадры предложены автоматически. Границы можно задать вручную.'))

    def choose_object_color(self):
        color=choose_color(self,QColor(self.object_hex.text()))
        if color.isValid():self.object_hex.setText(color.name().upper())

    def object_hex_changed(self):
        value='#'+self.object_hex.text().strip().lstrip('#')
        self.object_hex.setText(value.upper() if len(value)==7 and QColor(value).isValid() else '#287FE8')

    def link_material(self):
        name,ok=text_input(self,tr('Материал палитры'),tr('Название оттенка'),self.material_name.text())
        if ok and name.strip():
            self.material_name.setText(name.strip())
            self.palette_colors[name.strip()]=self.object_hex.text().lower()
            self.sync_controls();self.schedule_save()

    def apply_linked(self):
        name=self.material_name.text().strip();character=self.character_name.text().strip()
        if not name or self.worker:return
        targets=[(p,layer) for p in self.ordered() for layer in p.layers
                 if layer.material==name and layer.character==character and not layer.locked]
        if not targets:return
        dialog=QMessageBox(self);dialog.setWindowTitle(tr('Применить к связанным'))
        dialog.setText('\n'.join(f'{p.path.name} · {layer.name}' for p,layer in targets))
        yes=dialog.addButton(tr('Применить цвет'),QMessageBox.AcceptRole)
        dialog.addButton(tr('Отмена'),QMessageBox.RejectRole);dialog.exec()
        if dialog.clickedButton()!=yes:return
        color=QColor(self.object_hex.text())
        if not color.isValid():return
        for p,layer in targets:
            # Each page keeps an independent undoable trial, including non-active pages.
            if not p.trial:
                if p.uid==self.active:self.begin_trial(p)
                else:
                    from .chapter import atomic_file,version_path
                    p.trial={'options':p.options(),'selected':p.selected,'name':p.version_name}
                    prior=version_path(self.project,p.version()) if p.version() else p.path
                    with Image.open(prior) as image:
                        atomic_file(self.project.parent/'trials'/(p.uid+'.png'),lambda dest:image.save(dest,format='PNG'))
            layer.color=color.getRgb()[:3];layer.saturation=self.material_saturation.value()/100
            layer.lightness=self.material_light.value()/100;layer.dark_lift=self.material_dark.value()/100
        self.changed();self.persist()
        unique={p.uid:p for p,_ in targets}
        self.start(list(unique.values()))

    def reference_color(self):
        path,_=QFileDialog.getOpenFileName(self,tr('Цвет из референса'),'',tr('Страницы (*.png *.jpg *.jpeg)'))
        if not path:return
        from .reference import ReferenceDialog
        dialog=ReferenceDialog(path,self)
        if dialog.exec() and dialog.color.isValid():self.object_hex.setText(dialog.color.name().upper())

    def quality_report(self):
        p=self.current()
        if not p or self.canvas.result.isNull():return
        findings=audit(self.original,Image.fromqpixmap(self.canvas.result),p.layers)
        lines=[]
        for item in findings:
            kind=tr('Защищённые пиксели') if item['kind']=='protected' else tr('Остатки цвета') if item['kind']=='material' else tr('Мелкие фрагменты')
            lines.append(f"{item['object']} · {kind} · {item['pixels']}")
        linked={}
        for page in self.ordered():
            for layer in page.layers:
                if layer.material:
                    linked.setdefault((layer.character,layer.material),set()).add(tuple(layer.color))
        for (character,material),colors in linked.items():
            if len(colors)>1:lines.append(f'{character} · {material} · {tr("Палитра главы")} · {len(colors)}')
        text='\n'.join(lines) or tr('Добавьте объекты для проверки.')
        QMessageBox.information(self,tr('Проверить качество'),text+'\n\n'+tr('Это проверка областей, а не оценка художественной правильности.'))
