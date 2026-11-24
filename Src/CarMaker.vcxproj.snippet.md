# MSVC project edits for CMSumoCosim (office win64)

Edit **both** `CarMaker.vcxproj` and (optionally) `CarMaker.props` under `src/`.

## 1. Source files (`CarMaker.vcxproj`)

- ClCompile **User.cpp** (remove **User.c** if present).
- Link the `.a`.

## 2. CM version props

```xml
<Import Project="C:/IPG/carmaker/win64-14.1.1/include/MSVS_Defs.props" />
```

Same for `CarMakerInstall.vcxproj`.

## 3. Additional Include Directories (Debug|x64 and Release|x64)

Append:

```text
../include
C:/Program Files (x86)/Eclipse/Sumo/include
```

Example:

```xml
<ItemDefinitionGroup Condition="'$(Configuration)|$(Platform)'=='Release|x64'">
  <ClCompile>
    <AdditionalIncludeDirectories>
      $(CARMAKER_INC_DIR)/Car;$(CARMAKER_INC_DIR);$(MATSUPP_DIR)/include;
      C:/Program Files (x86)/Eclipse/Sumo/include;../include;%(AdditionalIncludeDirectories)
    </AdditionalIncludeDirectories>
  </ClCompile>
</ItemDefinitionGroup>
```

Repeat for Debug|x64.

## 4. Additional Library Directories

Append:

```text
C:/Program Files (x86)/Eclipse/Sumo/bin
../lib
```

## 5. Additional Dependencies

Append (order with existing CarMaker libs does not usually matter):

```text
libtracicpp.lib;libsumocpp.lib;../lib/CMSumoCosim_win64.a
```

Either in the vcxproj Link section **or** append to `CarMaker.props`:

```xml
<AdditionalLibraryDirectories>...(existing);C:/Program Files (x86)/Eclipse/Sumo/bin;../lib</AdditionalLibraryDirectories>
<AdditionalDependencies>...(existing);libtracicpp.lib;libsumocpp.lib;../lib/CMSumoCosim_win64.a</AdditionalDependencies>
```

## 6. Install project

Create `../bin` (project `bin/`) before Rebuild All, or build only the CarMaker project.

## 7. Verify

After a successful link, `src/CarMaker.win64.exe` exists. A missing `CMSumoCosim.h` or unresolved `CMSumoCosim_*` means steps 3 or 5 were skipped for that configuration.
