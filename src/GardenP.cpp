#include "Application.hpp"

int start() 
{
  int x = Application::ClearRegion();
  // x = sub_11CB18(x);
  // x = InitCtrRuntime(x);
  // x = sub_11CB8C(x);
  // x = sub_1019DC(x);
  // x = sub_11CAE4(x);
  // x = sub_11CB6C(x);
  // x = sub_11C7B4(x);

  __asm("SVC 3");
  return x;
}