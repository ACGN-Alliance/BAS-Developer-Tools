"""

使用av库解码的yuv420p视频帧渲染到QOpenGLWidget上

"""
import ctypes
from typing import Optional

import av  # 视频解码库
from OpenGL.GL import (
    GL_CLAMP_TO_EDGE,
    GL_COLOR_BUFFER_BIT,
    GL_DEPTH_BUFFER_BIT,
    GL_FLOAT,
    GL_LINEAR,
    GL_RED,
    GL_TEXTURE0,
    GL_TEXTURE1,
    GL_TEXTURE2,
    GL_TEXTURE_MAG_FILTER,
    GL_TEXTURE_MIN_FILTER,
    GL_TEXTURE_WRAP_S,
    GL_TEXTURE_WRAP_T,
    GL_TRIANGLE_STRIP,
    GL_UNSIGNED_BYTE,
    GL_DEPTH_TEST,
    GL_TEXTURE_2D,
    GL_UNPACK_ROW_LENGTH,
    glEnable,
    glClearColor,
    glClear,
    glViewport,
    glActiveTexture,
    glBindTexture,
    glTexImage2D,
    glTexParameteri,
    glUniform1i,
    glDrawArrays,
    glVertexAttribPointer,
    glEnableVertexAttribArray,
    glPixelStorei,
)
from PySide6.QtOpenGL import QOpenGLShader, QOpenGLShaderProgram, QOpenGLTexture
from PySide6.QtOpenGLWidgets import QOpenGLWidget

ATTRIB_VERTEX = 3
ATTRIB_TEXTURE = 4

vsh = """
#version 330 core
attribute vec4 vertexIn;
attribute vec2 textureIn;
varying vec2 textureOut;
void main(void)
{
    gl_Position = vertexIn;
    textureOut = textureIn;
}
"""

fsh = """
#version 330 core
varying vec2 textureOut;
uniform sampler2D tex_y;
uniform sampler2D tex_u;
uniform sampler2D tex_v;
void main(void)
{
    vec3 yuv;
    vec3 rgb;
    
    const vec3 Rcoeff = vec3(1.1644,  0.000,  1.7927);
    const vec3 Gcoeff = vec3(1.1644, -0.2132, -0.5329);
    const vec3 Bcoeff = vec3(1.1644,  2.1124,  0.000);
    
    yuv.x = texture2D(tex_y, textureOut).r;
    // 降低一些亮度
    // yuv.x = yuv.x - 0.0313; 
    
    yuv.y = texture2D(tex_u, textureOut).r - 0.5;
    yuv.z = texture2D(tex_v, textureOut).r - 0.5;
    rgb = mat3( 1,       1,         1,
                0,       -0.39465,  2.03211,
                1.13983, -0.58060,  0) * yuv;
    
    gl_FragColor = vec4(rgb, 1.0);
}
"""


class QYUVOpenGLWidget(QOpenGLWidget):
    def __init__(self, parent=None):
        QOpenGLWidget.__init__(self, parent)
        self.textureUniformY = 0
        self.textureUniformU = 0
        self.textureUniformV = 0
        self.id_y = 0
        self.id_u = 0
        self.id_v = 0
        self.m_pBufYuv420p = None
        self.m_pVShader = None
        self.m_pFShader = None
        self.m_pShaderProgram = None
        self.m_pTextureY = None
        self.m_pTextureU = None
        self.m_pTextureV = None
        self.m_nVideoH = 0
        self.m_nVideoW = 0

    def initializeGL(self):
        glEnable(GL_DEPTH_TEST)

        # compile shader
        self.m_pVShader = QOpenGLShader(QOpenGLShader.ShaderTypeBit.Vertex, self)

        self.m_pVShader.compileSourceCode(vsh)

        self.m_pFShader = QOpenGLShader(QOpenGLShader.ShaderTypeBit.Fragment, self)
        self.m_pFShader.compileSourceCode(fsh)
        # end compile shader

        # link shader
        self.m_pShaderProgram = QOpenGLShaderProgram(self)
        self.m_pShaderProgram.addShader(self.m_pVShader)
        self.m_pShaderProgram.addShader(self.m_pFShader)
        # bind attribute locations
        self.m_pShaderProgram.bindAttributeLocation("vertexIn", ATTRIB_VERTEX)
        self.m_pShaderProgram.bindAttributeLocation("textureIn", ATTRIB_TEXTURE)
        # link shader pipeline
        self.m_pShaderProgram.link()
        # bind shader pipeline for use
        self.m_pShaderProgram.bind()

        self.textureUniformY = self.m_pShaderProgram.uniformLocation("tex_y")
        self.textureUniformU = self.m_pShaderProgram.uniformLocation("tex_u")
        self.textureUniformV = self.m_pShaderProgram.uniformLocation("tex_v")

        # vertex matrix
        vertexVertices = ctypes.c_float * 8
        addr_vertexVertices = vertexVertices(
            -1.0,
            -1.0,  # Position 0
            1.0,
            -1.0,  # Position 1
            -1.0,
            1.0,  # Position 2
            1.0,
            1.0,  # Position 3
        )
        glVertexAttribPointer(
            ATTRIB_VERTEX,
            2,
            GL_FLOAT,
            0,
            0,
            ctypes.cast(addr_vertexVertices, ctypes.c_void_p),
        )
        glEnableVertexAttribArray(ATTRIB_VERTEX)

        # texture matrix
        textureVertices = ctypes.c_float * 8
        addr_textureVertices = textureVertices(
            0.0,
            1.0,  # TexCoord 0
            1.0,
            1.0,  # TexCoord 1
            0.0,
            0.0,  # TexCoord 2
            1.0,
            0.0,  # TexCoord 3
        )
        glVertexAttribPointer(
            ATTRIB_TEXTURE,
            2,
            GL_FLOAT,
            0,
            0,
            ctypes.cast(addr_textureVertices, ctypes.c_void_p),
        )
        glEnableVertexAttribArray(ATTRIB_TEXTURE)

        # create y u v texture
        self.m_pTextureY = QOpenGLTexture(QOpenGLTexture.Target2D)
        self.m_pTextureY.create()
        self.m_pTextureU = QOpenGLTexture(QOpenGLTexture.Target2D)
        self.m_pTextureU.create()
        self.m_pTextureV = QOpenGLTexture(QOpenGLTexture.Target2D)
        self.m_pTextureV.create()
        # end create y u v texture

        self.id_y = self.m_pTextureY.textureId()
        self.id_u = self.m_pTextureU.textureId()
        self.id_v = self.m_pTextureV.textureId()

        glClearColor(0.0, 0.0, 0.0, 1.0)  # black

    def hideEvent(self, event):
        self.m_pShaderProgram.removeAllShaders()
        self.m_pShaderProgram.release()
        self.m_pTextureY.destroy()
        self.m_pTextureU.destroy()
        self.m_pTextureV.destroy()
        QOpenGLWidget.hideEvent(self, event)

    def setFrame(self, pBufYuv420p: av.video.frame.VideoFrame):
        """
        使用av库的VideoFrame对象更新帧
        Args:
            pBufYuv420p:

        Returns:

        """
        if pBufYuv420p is None:
            return None
        self.m_pBufYuv420p = pBufYuv420p
        self.update()

    def initTexture(self, texture, texture_id, plane: av.video.plane.VideoPlane):
        glActiveTexture(texture)
        glBindTexture(GL_TEXTURE_2D, texture_id)
        glPixelStorei(GL_UNPACK_ROW_LENGTH, ctypes.c_int(plane.line_size))
        glTexImage2D(
            GL_TEXTURE_2D,
            0,
            GL_RED,
            plane.width,
            plane.height,
            0,
            GL_RED,
            GL_UNSIGNED_BYTE,
            ctypes.cast(
                plane.buffer_ptr, ctypes.c_void_p
            ),  # cast planeY.buffer_ptr to void*
        )
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)

    def paintGL(self):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        self.m_pBufYuv420p: Optional[av.video.frame.VideoFrame]
        if self.m_pBufYuv420p is not None:
            planeY: av.video.plane.VideoPlane = self.m_pBufYuv420p.planes[0]
            planeU: av.video.plane.VideoPlane = self.m_pBufYuv420p.planes[1]
            planeV: av.video.plane.VideoPlane = self.m_pBufYuv420p.planes[2]
            # Y
            self.initTexture(GL_TEXTURE0, self.id_y, planeY)
            # U
            self.initTexture(GL_TEXTURE1, self.id_u, planeU)
            # V
            self.initTexture(GL_TEXTURE2, self.id_v, planeV)

            glUniform1i(self.textureUniformY, 0)
            glUniform1i(self.textureUniformU, 1)
            glUniform1i(self.textureUniformV, 2)
            glDrawArrays(GL_TRIANGLE_STRIP, 0, 4)

    def resizeGL(self, w, h):
        if h == 0:
            h = 1
        glViewport(0, 0, w, h)
