#include "CoreMinimal.h"
#include "Modules/ModuleManager.h"
#include "Containers/Ticker.h"
#include "UObject/UObjectIterator.h"
#include "UObject/UnrealType.h"
#include "UObject/UObjectGlobals.h"
#include "Engine/UserDefinedEnum.h"
#include "Materials/Material.h"
#include "Materials/MaterialInstanceConstant.h"
#include "MaterialEditor/MaterialEditorInstanceConstant.h"
#include "MaterialEditor/DEditorScalarParameterValue.h"
#include "MaterialEditorModule.h"
#include "Kismet2/EnumEditorUtils.h"
#include "IDetailsView.h"
#include "PropertyEditorModule.h"
namespace {
const TCHAR* MasterPath = TEXT("/Game/VFX/Materials/Master/M_VFX_Master.M_VFX_Master");
FTSTicker::FDelegateHandle TickHandle;
FDelegateHandle PropertyChangedHandle;
bool ApplyingVisibility = false;
int32 VisibilityWrites = 0;
int32 DetailsRefreshes = 0;
int32 PropertySynchronizations = 0;
UMaterialInstanceConstant* GetSource(UMaterialEditorInstanceConstant* Editor) {
 FObjectPropertyBase* P = FindFProperty<FObjectPropertyBase>(Editor->GetClass(), TEXT("SourceInstance"));
 return P ? Cast<UMaterialInstanceConstant>(P->GetObjectPropertyValue_InContainer(Editor)) : nullptr;
}
int32 ApplyVisibility(UMaterialEditorInstanceConstant* Editor) {
 if (ApplyingVisibility) return 0;
 TGuardValue<bool> Guard(ApplyingVisibility, true);
 UMaterialInstanceConstant* Source = GetSource(Editor);
 if (!Source || !Source->GetMaterial() || Source->GetMaterial()->GetPathName() != MasterPath) return 0;
 bool Regenerate = false;
 for (const FEditorParameterGroup& Group : Editor->ParameterGroups) {
  for (UDEditorParameterValue* Parameter : Group.Parameters) {
   auto* Scalar = Cast<UDEditorScalarParameterValue>(Parameter);
   if (Scalar && Scalar->ParameterInfo.Name == FName(TEXT("折射控制方式")) && Scalar->Enumeration.ToSoftObjectPath().ToString() != TEXT("/Game/VFX/Materials/Master/E_VFX_RefractionMode.E_VFX_RefractionMode")) Regenerate = true;
  }
 }
 if (Regenerate) {
  Editor->RegenerateArrays();
  if (TSharedPtr<IDetailsView> Details = Editor->DetailsView.Pin()) {
   ++DetailsRefreshes;
   Details->ForceRefresh();
  }
 }
 TArray<FMaterialParameterInfo> Visible;
 IMaterialEditorModule::Get().GetVisibleMaterialParameters(Source->GetMaterial(), Source, Visible);
 float Mode = 0.0f;
 Source->GetScalarParameterValue(FMaterialParameterInfo(TEXT("折射控制方式")), Mode);
 Visible.RemoveAll([Mode](const FMaterialParameterInfo& Info) {
  const FString Name = Info.Name.ToString();
  if (Mode < 0.5f) return Name == TEXT("折射贴图") || Name == TEXT("折射 平铺偏移") || Name == TEXT("折射 速度UV/旋转/极坐标");
  if (Mode < 1.5f) return Name == TEXT("折射 使用通道?") || Name == TEXT("折射 控制通道(RGBA)");
  return false;
 });
 FArrayProperty* P = FindFProperty<FArrayProperty>(Editor->GetClass(), TEXT("VisibleExpressions"));
 if (!P) return 0;
 auto& Actual = *P->ContainerPtrToValuePtr<TArray<FMaterialParameterInfo>>(Editor);
 if (Actual != Visible) {
  Actual = MoveTemp(Visible);
  ++VisibilityWrites;
  // Parameter rows bind their visibility to this array and update themselves.
  // ForceRefresh here destroys active numeric inputs and interrupts dragging.
 }
 return 1;
}
void OnPropertyChanged(UObject* Object, FPropertyChangedEvent&) {
 if (!Object || ApplyingVisibility || !IsInGameThread() ||
     (!Object->IsA<UMaterialEditorInstanceConstant>() && !Object->IsA<UMaterialInstanceConstant>())) return;
 for (TObjectIterator<UMaterialEditorInstanceConstant> It; It; ++It) {
  if (IsValid(*It) && !It->HasAnyFlags(RF_ClassDefaultObject) && It->DetailsView.IsValid() &&
      (Object == *It || Object == GetSource(*It))) {
   // CopyToSourceInstance resets visibility even for interactive numeric edits.
   // Repair it before Slate can observe unfiltered rows and recreate widgets.
   PropertySynchronizations += ApplyVisibility(*It);
  }
 }
}
bool OnTick(float) {
 for (TObjectIterator<UMaterialEditorInstanceConstant> It; It; ++It)
  if (IsValid(*It) && !It->HasAnyFlags(RF_ClassDefaultObject) && It->DetailsView.IsValid()) ApplyVisibility(*It);
 return true;
}
}
extern "C" __declspec(dllexport) int32 VFX_Start() {
 if (!IsInGameThread()) return -1;
 if (!PropertyChangedHandle.IsValid()) PropertyChangedHandle = FCoreUObjectDelegates::OnObjectPropertyChanged.AddStatic(&OnPropertyChanged);
 if (!TickHandle.IsValid()) TickHandle=FTSTicker::GetCoreTicker().AddTicker(FTickerDelegate::CreateStatic(&OnTick),0.2f);
 OnTick(0.0f); return 1;
}
extern "C" __declspec(dllexport) void VFX_Stop() {
 FCoreUObjectDelegates::OnObjectPropertyChanged.Remove(PropertyChangedHandle);
 PropertyChangedHandle.Reset();
 if (TickHandle.IsValid()) FTSTicker::GetCoreTicker().RemoveTicker(TickHandle);
 TickHandle.Reset();
}
extern "C" __declspec(dllexport) int32 VFX_Refresh() {
 if (!IsInGameThread()) return -1;
 int32 Count=0;
 for (TObjectIterator<UMaterialEditorInstanceConstant> It; It; ++It)
  if (IsValid(*It) && !It->HasAnyFlags(RF_ClassDefaultObject)) Count+=ApplyVisibility(*It);
 return Count;
}
extern "C" __declspec(dllexport) int32 VFX_GetDetailsRefreshCount() { return DetailsRefreshes; }
extern "C" __declspec(dllexport) int32 VFX_GetVisibilityWriteCount() { return VisibilityWrites; }
extern "C" __declspec(dllexport) int32 VFX_GetPropertySyncCount() { return PropertySynchronizations; }
// Run the actual numeric-edit copy/notification path on a transient editor only.
// This check cannot change project assets or the user's open editor values.
extern "C" __declspec(dllexport) int32 VFX_TestTransientNumericEdits(const TCHAR* EditorPath) {
 if (!IsInGameThread()) return -1;
 auto* Editor = FindObject<UMaterialEditorInstanceConstant>(nullptr, EditorPath);
 auto* Source = Editor ? GetSource(Editor) : nullptr;
 if (!Source || Source->GetOutermost() != GetTransientPackage() || Editor->DetailsView.IsValid()) return -2;
 ApplyVisibility(Editor);
 auto& PropertyEditor = FModuleManager::LoadModuleChecked<FPropertyEditorModule>(TEXT("PropertyEditor"));
 FDetailsViewArgs Args;
 Args.bUpdatesFromSelection = false;
 TSharedRef<IDetailsView> Details = PropertyEditor.CreateDetailView(Args);
 Details->SetObject(Editor);
 Editor->DetailsView = Details;
 const int32 BeforeRefreshes = DetailsRefreshes;
 const int32 BeforeSync = PropertySynchronizations;
 FArrayProperty* P = FindFProperty<FArrayProperty>(Editor->GetClass(), TEXT("VisibleExpressions"));
 const auto BeforeVisible = *P->ContainerPtrToValuePtr<TArray<FMaterialParameterInfo>>(Editor);
 int32 Edits = 0;
 for (const FEditorParameterGroup& Group : Editor->ParameterGroups) {
  for (UDEditorParameterValue* Parameter : Group.Parameters) {
   auto* Scalar = Cast<UDEditorScalarParameterValue>(Parameter);
   if (!Scalar || !Scalar->Enumeration.IsNull() || !BeforeVisible.Contains(Scalar->ParameterInfo)) continue;
   const float Before = Scalar->ParameterValue;
   const bool BeforeOverride = Scalar->bOverride;
   Scalar->bOverride = true;
   for (int32 Index = 0; Index < 8; ++Index) {
    Scalar->ParameterValue = Before + Index * 0.01f;
    Editor->CopyToSourceInstance();
    FPropertyChangedEvent Event(FindFProperty<FProperty>(Scalar->GetClass(), TEXT("ParameterValue")), EPropertyChangeType::Interactive);
    Source->PostEditChangeProperty(Event);
    const auto& Actual = *P->ContainerPtrToValuePtr<TArray<FMaterialParameterInfo>>(Editor);
    if (DetailsRefreshes != BeforeRefreshes || Actual != BeforeVisible) {
     Editor->DetailsView.Reset();
     return -3;
    }
    ++Edits;
   }
   Scalar->ParameterValue = Before;
   Scalar->bOverride = BeforeOverride;
  }
 }
 Editor->CopyToSourceInstance();
 ApplyVisibility(Editor);
 Editor->DetailsView.Reset();
 if (PropertySynchronizations - BeforeSync != Edits) return -4;
 return Edits;
}
extern "C" __declspec(dllexport) int32 VFX_CreateRefractionEnum() {
 if (!IsInGameThread()) return -1;
 const TCHAR* EnumPath=TEXT("/Game/VFX/Materials/Master/E_VFX_RefractionMode.E_VFX_RefractionMode");
 if (LoadObject<UUserDefinedEnum>(nullptr,EnumPath)) return 1;
 UPackage* Package=CreatePackage(TEXT("/Game/VFX/Materials/Master/E_VFX_RefractionMode"));
 auto* Enum=Cast<UUserDefinedEnum>(FEnumEditorUtils::CreateUserDefinedEnum(Package,TEXT("E_VFX_RefractionMode"),RF_Public|RF_Standalone|RF_Transactional));
 if (!Enum) return -2;
 while (Enum->NumEnums()<5) FEnumEditorUtils::AddNewEnumeratorForUserDefinedEnum(Enum);
 const TCHAR* Labels[]={TEXT("通道"),TEXT("贴图"),TEXT("通道 × 贴图"),TEXT("通道 + 贴图")};
 for (int32 Index=0;Index<4;++Index)
  if (!FEnumEditorUtils::SetEnumeratorDisplayName(Enum,Index,FText::FromString(Labels[Index]))) return -3;
 Package->MarkPackageDirty(); return 1;
}
class FVFXMaterialControlsModule:public IModuleInterface {
public:
 virtual void StartupModule() override {VFX_Start();UE_LOG(LogTemp,Display,TEXT("VFXMaterialControls started automatically"));}
 virtual void ShutdownModule() override {VFX_Stop();}
};
IMPLEMENT_MODULE(FVFXMaterialControlsModule,VFXMaterialControls)

