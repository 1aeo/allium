#!/usr/bin/env python3
"""
Simple Validation System for AROI Leaderboard Optimizations

This script validates that:
1. AROI leaderboards are generated successfully
2. Template optimizations are in place
3. Country processing optimization is present
4. Performance is acceptable
5. Output quality is maintained
"""

import os
import sys
import time
import subprocess
import json
from pathlib import Path
from bs4 import BeautifulSoup

def run_validation():
    """Run comprehensive validation of AROI leaderboard optimizations"""
    
    print("🚀 AROI Leaderboard Validation Suite")
    print("="*60)
    
    results = []
    
    # Test 1: Generate AROI leaderboards
    print("📋 Test 1: Generating AROI leaderboards...")
    start_time = time.time()
    
    try:
        os.chdir("allium")
        result = subprocess.run(
            [sys.executable, "allium.py", "--out", "www_validation_test"],
            capture_output=True,
            text=True,
            timeout=300
        )
        generation_time = time.time() - start_time
        
        if result.returncode == 0:
            aroi_file = Path("www_validation_test/misc/aroi-leaderboards.html")
            if aroi_file.exists():
                file_size = aroi_file.stat().st_size
                print(f"   ✅ AROI leaderboards generated successfully")
                print(f"   📏 File size: {file_size:,} bytes")
                print(f"   ⏱️  Generation time: {generation_time:.2f}s")
                results.append({
                    "test": "aroi_generation",
                    "status": "PASSED",
                    "details": {
                        "file_size": file_size,
                        "generation_time": generation_time
                    }
                })
            else:
                print(f"   ❌ AROI file not found at expected location")
                results.append({"test": "aroi_generation", "status": "FAILED"})
                return results
        else:
            print(f"   ❌ allium.py failed with return code {result.returncode}")
            print(f"   Error: {result.stderr}")
            results.append({"test": "aroi_generation", "status": "FAILED"})
            return results
            
    except Exception as e:
        print(f"   ❌ Error during generation: {e}")
        results.append({"test": "aroi_generation", "status": "FAILED"})
        return results
    
    # Test 2: Validate HTML structure and content
    print("\n🔍 Test 2: Validating HTML structure...")
    try:
        with open("www_validation_test/misc/aroi-leaderboards.html", 'r', encoding='utf-8') as f:
            content = f.read()
            soup = BeautifulSoup(content, 'html.parser')
        
        # Count key elements
        tables = soup.find_all('table')
        badges = soup.find_all('span', class_='badge')
        rank_badges = soup.find_all('span', class_='rank-badge')
        operator_links = soup.find_all('a', href=True)
        
        print(f"   📊 Tables found: {len(tables)}")
        print(f"   🏆 Champion badges: {len(badges)}")
        print(f"   🥇 Rank badges: {len(rank_badges)}")
        print(f"   🔗 Operator links: {len(operator_links)}")
        
        # Validate minimum expected content
        if len(tables) >= 10 and len(badges) >= 5:
            print(f"   ✅ HTML structure validation passed")
            results.append({
                "test": "html_structure",
                "status": "PASSED",
                "details": {
                    "tables": len(tables),
                    "badges": len(badges),
                    "rank_badges": len(rank_badges),
                    "operator_links": len(operator_links)
                }
            })
        else:
            print(f"   ❌ Insufficient content found")
            results.append({"test": "html_structure", "status": "FAILED"})
            
    except Exception as e:
        print(f"   ❌ Error parsing HTML: {e}")
        results.append({"test": "html_structure", "status": "FAILED"})
    
    # Test 3: Validate template optimizations
    print("\n🎨 Test 3: Validating template optimizations...")
    try:
        macro_file = Path("templates/aroi_macros.html")
        main_template = Path("templates/aroi-leaderboards.html")
        
        if not macro_file.exists():
            print(f"   ❌ Macro file not found: {macro_file}")
            results.append({"test": "template_optimizations", "status": "FAILED"})
        elif not main_template.exists():
            print(f"   ❌ Main template not found: {main_template}")
            results.append({"test": "template_optimizations", "status": "FAILED"})
        else:
            with open(main_template, 'r', encoding='utf-8') as f:
                template_content = f.read()
            
            # Check for macro usage
            macros_used = []
            key_macros = ['champion_badge', 'top3_table', 'rank_badge', 'operator_link', 'generic_ranking_table']
            
            for macro in key_macros:
                if macro in template_content:
                    macros_used.append(macro)
            
            template_lines = len(template_content.split('\n'))
            
            print(f"   📄 Template lines: {template_lines}")
            print(f"   🔧 Macros used: {len(macros_used)}/{len(key_macros)}")
            print(f"   📝 Macros found: {', '.join(macros_used)}")
            
            if len(macros_used) >= 3:
                print(f"   ✅ Template optimization validation passed")
                results.append({
                    "test": "template_optimizations",
                    "status": "PASSED",
                    "details": {
                        "template_lines": template_lines,
                        "macros_used": macros_used,
                        "macro_count": len(macros_used)
                    }
                })
            else:
                print(f"   ⚠️  Limited macro usage detected")
                results.append({"test": "template_optimizations", "status": "WARNING"})
                
    except Exception as e:
        print(f"   ❌ Error checking templates: {e}")
        results.append({"test": "template_optimizations", "status": "FAILED"})
    
    # Test 4: Validate country processing optimization
    print("\n🌍 Test 4: Validating country processing optimization...")
    try:
        aroileaders_file = Path("lib/aroileaders.py")
        
        if not aroileaders_file.exists():
            print(f"   ❌ aroileaders.py not found")
            results.append({"test": "country_optimization", "status": "FAILED"})
        else:
            with open(aroileaders_file, 'r', encoding='utf-8') as f:
                code_content = f.read()
            
            # Check for optimization patterns
            if "get_rare_countries_weighted_with_existing_data" in code_content:
                # Look for pre-calculation pattern
                lines = code_content.split('\n')
                for i, line in enumerate(lines):
                    if "rare_countries_data" in line and "=" in line:
                        context = '\n'.join(lines[max(0, i-2):i+3])
                        if "get_rare_countries_weighted_with_existing_data" in context:
                            print(f"   ✅ Country processing pre-calculation found")
                            print(f"   🎯 Optimization pattern detected at line ~{i+1}")
                            results.append({
                                "test": "country_optimization",
                                "status": "PASSED",
                                "details": {"optimization_line": i+1}
                            })
                            break
                else:
                    print(f"   ⚠️  Country processing function found but optimization unclear")
                    results.append({"test": "country_optimization", "status": "WARNING"})
            else:
                print(f"   ⚠️  Country processing function not found")
                results.append({"test": "country_optimization", "status": "WARNING"})
                
    except Exception as e:
        print(f"   ❌ Error checking country optimization: {e}")
        results.append({"test": "country_optimization", "status": "FAILED"})
    
    # Test 5: Performance baseline
    print("\n⚡ Test 5: Performance validation...")
    try:
        # Re-run for timing
        start_time = time.time()
        result = subprocess.run(
            [sys.executable, "allium.py", "--out", "www_perf_test"],
            capture_output=True,
            text=True,
            timeout=300
        )
        execution_time = time.time() - start_time
        
        if result.returncode == 0:
            print(f"   ⏱️  Execution time: {execution_time:.2f}s")
            
            # Performance thresholds (generous for validation)
            if execution_time < 120:  # Under 2 minutes
                print(f"   ✅ Performance validation passed")
                results.append({
                    "test": "performance",
                    "status": "PASSED",
                    "details": {"execution_time": execution_time}
                })
            else:
                print(f"   ⚠️  Slow performance detected")
                results.append({"test": "performance", "status": "WARNING"})
        else:
            print(f"   ❌ Performance test failed")
            results.append({"test": "performance", "status": "FAILED"})
            
    except Exception as e:
        print(f"   ❌ Error during performance test: {e}")
        results.append({"test": "performance", "status": "FAILED"})
    
    # Cleanup
    print("\n🧹 Cleaning up test files...")
    try:
        import shutil
        for test_dir in ["www_validation_test", "www_perf_test"]:
            if Path(test_dir).exists():
                shutil.rmtree(test_dir)
        print(f"   ✅ Cleanup completed")
    except Exception as e:
        print(f"   ⚠️  Cleanup warning: {e}")
    
    # Summary
    print("\n" + "="*60)
    print("VALIDATION SUMMARY")
    print("="*60)
    
    passed = sum(1 for r in results if r["status"] == "PASSED")
    failed = sum(1 for r in results if r["status"] == "FAILED") 
    warnings = sum(1 for r in results if r["status"] == "WARNING")
    
    print(f"✅ PASSED: {passed}")
    print(f"❌ FAILED: {failed}")
    print(f"⚠️  WARNINGS: {warnings}")
    print(f"📊 TOTAL: {len(results)}")
    
    if failed == 0:
        print(f"\n🎉 ALL VALIDATIONS PASSED!")
        print("Your AROI leaderboard optimizations are working correctly.")
        success = True
    else:
        print(f"\n⚠️  VALIDATION ISSUES DETECTED")
        print("Review failed tests and fix issues before proceeding.")
        success = False
    
    # Save results
    result_data = {
        "timestamp": time.time(),
        "success": success,
        "summary": {"passed": passed, "failed": failed, "warnings": warnings},
        "tests": results
    }
    
    os.chdir("..")  # Back to main directory
    with open("simple_validation_results.json", "w") as f:
        json.dump(result_data, f, indent=2)
    
    print(f"\n📄 Results saved to: simple_validation_results.json")
    
    return success

if __name__ == "__main__":
    success = run_validation()
    sys.exit(0 if success else 1) 