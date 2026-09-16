function bin_map = phasevariance_nonlin_v2(mask, phase, radius, resolution)
% Description: Script to calculate phase reliability maps (to remove voxels in the vicinity of sinuses)
%
% Authors: Chaoyue Wang, Benjamin C. Tendler & Karla L. Miller
%
% Copyright 2021 University of Oxford
%
% Licensed under the Apache License, Version 2.0 (the "License");
% you may not use this file except in compliance with the License.
% You may obtain a copy of the License at
%
% http://www.apache.org/licenses/LICENSE-2.0
%
% Unless required by applicable law or agreed to in writing, software
% distributed under the License is distributed on an "AS IS" BASIS,
% WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
% See the License for the specific language governing permissions and
% limitations under the License.

% radius (of the kernel to be used) in mm e.g. 3mm

% resolution (of the data) in mm e.g. [0.8 0.8 3] (UK Biobank swMRI)

    dim = size(phase);


    rx = resolution(1);
    ry = resolution(2);
    rz = resolution(3);

    factorX = round(rx * 10); 
    factorY = round(ry * 10);
    factorZ = round(rz * 10);

    factorXY = round(factorY/factorX);
    factorXZ = round(factorZ/factorX);

    padX = mod(dim(1), factorX);
    padY = mod(dim(2), factorY);
    padZ = mod(dim(3), factorZ);

    if padX > 0
        padX = factorX - padX;
    else
        padX = 0;
    end

    if padY > 0
        padY = factorY - padY;
    else
        padY = 0;
    end

    if padZ > 0
        padZ = factorZ - padZ;
    else
        padZ = 0;
    end

    phase2 = zeros(dim(1) + padX, dim(2) + padY, dim(3) + padZ);
    mask2 = zeros(dim(1) + padX, dim(2) + padY, dim(3) + padZ);
    
    phase2(1:dim(1), 1:dim(2), 1:dim(3)) = phase;
    mask2(1:dim(1), 1:dim(2), 1:dim(3)) = mask;
    
    phase = phase2;
    mask = mask2;
    clear phase2 mask2;

    dim = size(phase);  

    [cy, cx, cz] = meshgrid( ...
        double( -dim(2)*factorXY/2 : (dim(2)*factorXY/2 - 1) ), ...
        double( -dim(1)/2 : (dim(1)/2 - 1) ), ...
        double( -dim(3)*factorXZ/2 : (dim(3)*factorXZ/2 - 1) ) ...
    );


    index = (cx.^2 + cy.^2 + cz.^2) <= (radius * 10)^2;

    rho_temp = zeros(size(cx), 'double');
    rho_temp(index) = 1;

    clear index cx cy cz

    dimX = dim(1)/factorX;
    dimY = dim(2)/factorY*factorXY;
    dimZ = dim(3)/factorZ*factorXZ;  

    X = repmat(factorX, 1, dimX);
    Y = repmat(factorY, 1, dimY);
    Z = repmat(factorZ, 1, dimZ);


    A = mat2cell(rho_temp, X, Y, Z);
    rho_temp = cellfun(@(blk) mean(blk(:)), A);

    rho = double(zeros(dim));
    rho(((dim(1)-dimX)/2+1):((dim(1)-dimX)/2+dimX),((dim(2)-dimY)/2+1):((dim(2)-dimY)/2+dimY),((dim(3)-dimZ)/2+1):((dim(3)-dimZ)/2+dimZ))=rho_temp;

    cdata = exp(1i*phase) .* mask;

    cdatalp = fftshift(ifftn(fftn(cdata) .* fftn(rho)));
    fz      = abs(cdatalp);

    fm_conv = fftshift(ifftn(fftn(mask) .* fftn(rho)));
    fm      = abs(fm_conv);  

    bin_map = fz ./ (fm + eps);
    bin_map(mask == 0) = 1;

    bin_map = bin_map(1:(dim(1) - padX), 1:(dim(2) -padY), 1:(dim(3) - padZ));

end
